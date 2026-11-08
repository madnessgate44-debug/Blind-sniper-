#!/usr/bin/env python3
"""Single-run, read-only executor for a fixed command allowlist."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_runtime as runtime  # noqa: E402
from blind_sniper_ledger import TaskLedger  # noqa: E402

ALLOWLIST = {
    "unit-tests": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
    "runtime-validator": [sys.executable, "scripts/validate_blind_sniper_runtime.py"],
}


def server_now(repository: str):
    request = Request(
        f"https://api.github.com/repos/{repository}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Blind-Sniper-Executor"},
    )
    with urlopen(request, timeout=15) as response:
        value = response.headers.get("Date")
    if not value:
        raise RuntimeError("GitHub response Date header missing; refusing to use runner clock")
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def append_lease_transition(ledger, state, owner_id, key, repository):
    payload = runtime.build_state_event_payload(ledger, state)
    return ledger.append_transition_if_lease(
        task_id=state["task_id"], owner_id=owner_id, payload=payload,
        idempotency_key=key, now=server_now(repository),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "executor.log"
    receipt_path = output / "receipt.json"
    receipt = {
        "task_id": None, "branch": args.branch, "commit_sha": args.commit,
        "run_id": args.run_id, "commands": [], "status": "BLOCKED",
        "review_status": "NOT_REACHED",
    }

    try:
        task_path = (ROOT / args.task_file).resolve()
        if not task_path.is_relative_to(ROOT):
            raise RuntimeError("Task file must remain inside the repository")
        task = json.loads(task_path.read_text(encoding="utf-8"))
        if set(task) != {"task_id", "objective", "branch", "commands"}:
            raise RuntimeError("Task file must contain exactly task_id, objective, branch and commands")
        if task["branch"] != args.branch or os.environ.get("GITHUB_REF_NAME") != args.branch:
            raise RuntimeError("Task branch does not match the checked-out named branch")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", str(task["task_id"])):
            raise RuntimeError("Invalid task_id")
        if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
            raise RuntimeError("A full commit SHA is required")
        if not re.fullmatch(r"[0-9]+", args.run_id):
            raise RuntimeError("Invalid workflow run ID")
        command_ids = task["commands"]
        if not isinstance(command_ids, list) or not command_ids or any(x not in ALLOWLIST for x in command_ids):
            raise RuntimeError("Task contains an empty or non-allowlisted command list")
        if len(command_ids) != len(set(command_ids)):
            raise RuntimeError("Duplicate command IDs are not permitted")

        repository = os.environ["GITHUB_REPOSITORY"]
        instant = server_now(repository)
        task_id = str(task["task_id"])
        owner_id = "blind-sniper-executor"
        receipt["task_id"] = task_id
        ledger = TaskLedger(output / "events.jsonl")

        plan = runtime.build_plan({
            "task_id": task_id,
            "objective": task["objective"],
            "repository": repository,
            "base_commit": args.commit,
        })
        state = runtime.create_task_state(plan)
        runtime.persist_task_state(
            ledger, state, event_type="TASK_CREATED",
            idempotency_key=f"{task_id}:created:{args.run_id}",
        )
        for status in ("INSPECTING", "SPECIFIED", "PLANNED"):
            state = runtime.transition_task(state, status)
            runtime.persist_task_state(
                ledger, state, event_type="TASK_TRANSITIONED",
                idempotency_key=f"{task_id}:{status}:{args.run_id}",
            )

        claim = ledger.claim_task(
            task_id=task_id, owner_id=owner_id, lease_seconds=3600,
            idempotency_key=f"{task_id}:claim:{args.run_id}", now=instant,
        )
        if not claim["claimed"]:
            raise RuntimeError("Task lease could not be reserved")
        state = runtime.transition_task(state, "EXECUTING")
        state["implementer_id"] = owner_id
        append_lease_transition(ledger, state, owner_id, f"{task_id}:execute:{args.run_id}", repository)
        receipt["status"] = "EXECUTING"
        safe_env = {"PATH": os.environ.get("PATH", ""), "PYTHONUNBUFFERED": "1"}

        with log_path.open("w", encoding="utf-8") as log:
            for position, command_id in enumerate(command_ids, start=1):
                renewed = ledger.claim_task(
                    task_id=task_id, owner_id=owner_id, lease_seconds=3600,
                    idempotency_key=f"{task_id}:renew:{args.run_id}:{position}",
                    now=server_now(repository),
                )
                if not renewed["claimed"]:
                    raise RuntimeError("Active task lease could not be renewed")
                command = ALLOWLIST[command_id]
                log.write(f"COMMAND {position}: {command_id}\n")
                log.flush()
                result = subprocess.run(
                    command, cwd=ROOT, env=safe_env, capture_output=True,
                    text=True, timeout=600, check=False,
                )
                log.write(result.stdout or "")
                log.write(result.stderr or "")
                log.write(f"\nEXIT_CODE: {result.returncode}\n")
                log.flush()
                receipt["commands"].append({
                    "command_id": command_id,
                    "exit_code": result.returncode,
                })

        passed = all(row["exit_code"] == 0 for row in receipt["commands"])
        target = "VERIFYING" if passed else "FAILED"
        state = runtime.transition_task(state, target)
        append_lease_transition(ledger, state, owner_id, f"{task_id}:{target}:{args.run_id}", repository)
        if passed:
            state = runtime.transition_task(
                state, "REVIEWING", {"verification_passed": True},
            )
            append_lease_transition(ledger, state, owner_id, f"{task_id}:REVIEWING:{args.run_id}", repository)
            receipt["status"] = "REVIEWING"
            receipt["review_status"] = "AWAITING_INDEPENDENT_REVIEW"
        else:
            receipt["status"] = "FAILED"
            receipt["review_status"] = "NOT_REACHED"
        receipt["server_time_source"] = "GitHub HTTP Date header"
        receipt["lease_owner"] = owner_id
        receipt["lease_expires_at"] = ledger.lease_status(task_id, server_now(repository))["lease_expires_at"]
        receipt["state"] = state
        receipt["exit_code"] = 0 if passed else 1
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        receipt["exit_code"] = 2
    finally:
        receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return int(receipt.get("exit_code", 2))


if __name__ == "__main__":
    raise SystemExit(main())
