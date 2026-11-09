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
COMMAND_STEPS = {
    "unit-tests": "run_unit_tests",
    "runtime-validator": "run_runtime_validator",
}
WORKFLOW_ID = "bounded-verification"
COMMAND_TIMEOUT_SECONDS = 600


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


def count_log_lines(path):
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def update_step(plan, step_id, **fields):
    matches = [step for step in plan["steps"] if step["id"] == step_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one planned step named {step_id}")
    matches[0].update(fields)
    return matches[0]


def append_step_receipt(ledger, state, owner_id, step_id, event, repository):
    state["events"].append({
        "from": "EXECUTING",
        "to": "EXECUTING",
        "at": event["at"],
        "evidence": {"step_id": step_id, "step_status": event["status"], "run_id": event["run_id"]},
    })
    append_lease_transition(
        ledger, state, owner_id,
        f'{state["task_id"]}:step:{step_id}:{event["status"]}:{event["run_id"]}:{len(state["events"])}',
        repository,
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
        "run_id": args.run_id, "commands": [], "steps": [], "status": "BLOCKED",
        "review_status": "NOT_REACHED",
        "reservation_scope": "single_workflow_run_artifact",
        "cross_run_exclusion": False,
        "cross_run_deduplication": False,
        "artifact_retention_days": 14,
    }

    try:
        task_path = (ROOT / args.task_file).resolve()
        if not task_path.is_relative_to(ROOT):
            raise RuntimeError("Task file must remain inside the repository")
        task = json.loads(task_path.read_text(encoding="utf-8"))
        if set(task) != {"task_id", "objective", "branch", "commands", "workflow"}:
            raise RuntimeError("Task file must contain exactly task_id, objective, branch, commands and workflow")
        if task["workflow"] != WORKFLOW_ID:
            raise RuntimeError(f"Task workflow must be {WORKFLOW_ID}")
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
            "workflow": task["workflow"],
            "repository": repository,
            "base_commit": args.commit,
        })
        for command_id, step_id in COMMAND_STEPS.items():
            if command_id not in command_ids:
                update_step(plan, step_id, status="NOT_REQUESTED", reason="Command not present in this task envelope")
        update_step(plan, "await_independent_review", status="AWAITING_INDEPENDENT_REVIEW",
                    reason="Requires a distinct reviewer; executor cannot self-approve")
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
            raise RuntimeError("Task lease could not be reserved in this run's local ledger")
        state = runtime.transition_task(state, "EXECUTING")
        state["implementer_id"] = owner_id
        append_lease_transition(ledger, state, owner_id, f"{task_id}:execute:{args.run_id}", repository)
        receipt["status"] = "EXECUTING"
        safe_env = {"PATH": os.environ.get("PATH", ""), "PYTHONUNBUFFERED": "1"}
        failed = False
        with log_path.open("w", encoding="utf-8") as log:
            for position, command_id in enumerate(command_ids, start=1):
                step_id = COMMAND_STEPS[command_id]
                renewed = ledger.claim_task(
                    task_id=task_id, owner_id=owner_id, lease_seconds=3600,
                    idempotency_key=f"{task_id}:renew:{args.run_id}:{position}",
                    now=server_now(repository),
                )
                if not renewed["claimed"]:
                    raise RuntimeError("Active task lease could not be renewed")
                started = server_now(repository).isoformat()
                start_line = count_log_lines(log_path) + 1
                update_step(plan, step_id, status="RUNNING", started_at=started,
                            run_id=args.run_id, commit_sha=args.commit)
                event = {"at": started, "status": "RUNNING", "run_id": args.run_id}
                append_step_receipt(ledger, state, owner_id, step_id, event, repository)

                command = ALLOWLIST[command_id]
                header = f"COMMAND {position}: {command_id}\n"
                log.write(header)
                log.flush()
                try:
                    result = subprocess.run(
                        command, cwd=ROOT, env=safe_env, capture_output=True,
                        text=True, timeout=COMMAND_TIMEOUT_SECONDS, check=False,
                    )
                    stdout = result.stdout or ""
                    stderr = result.stderr or ""
                    log.write(stdout)
                    log.write(stderr)
                    completed = server_now(repository).isoformat()
                    log.write(f"\nEXIT_CODE: {result.returncode}\n")
                    log.flush()
                    end_line = count_log_lines(log_path)
                    status = "PASS" if result.returncode == 0 else "FAIL"
                    step_fields = {
                        "status": status, "exit_code": result.returncode,
                        "completed_at": completed, "log_ref": "executor.log",
                        "log_start_line": start_line, "log_end_line": end_line,
                    }
                    command_row = {
                        "command_id": command_id, "workflow_step_id": step_id,
                        "status": status, "exit_code": result.returncode,
                        "started_at": started, "completed_at": completed,
                        "log_ref": "executor.log", "log_start_line": start_line,
                        "log_end_line": end_line,
                    }
                    failed = result.returncode != 0
                except subprocess.TimeoutExpired as exc:
                    completed = server_now(repository).isoformat()
                    stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                    stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                    log.write(stdout + stderr + f"\nTIMEOUT after {COMMAND_TIMEOUT_SECONDS} seconds\n")
                    log.flush()
                    end_line = count_log_lines(log_path)
                    step_fields = {
                        "status": "TIMED_OUT", "completed_at": completed,
                        "timeout_seconds": COMMAND_TIMEOUT_SECONDS, "log_ref": "executor.log",
                        "log_start_line": start_line, "log_end_line": end_line,
                    }
                    command_row = {
                        "command_id": command_id, "workflow_step_id": step_id,
                        "status": "TIMED_OUT", "exit_code": None,
                        "started_at": started, "completed_at": completed,
                        "timeout_seconds": COMMAND_TIMEOUT_SECONDS, "log_ref": "executor.log",
                        "log_start_line": start_line, "log_end_line": end_line,
                    }
                    failed = True
                except Exception as exc:
                    completed = server_now(repository).isoformat()
                    log.write(f"\nEXECUTION_ERROR: {type(exc).__name__}: {exc}\n")
                    log.flush()
                    end_line = count_log_lines(log_path)
                    step_fields = {
                        "status": "ERROR", "completed_at": completed,
                        "error": f"{type(exc).__name__}: {exc}", "log_ref": "executor.log",
                        "log_start_line": start_line, "log_end_line": end_line,
                    }
                    command_row = {
                        "command_id": command_id, "workflow_step_id": step_id,
                        "status": "ERROR", "exit_code": None,
                        "started_at": started, "completed_at": completed,
                        "error": f"{type(exc).__name__}: {exc}", "log_ref": "executor.log",
                        "log_start_line": start_line, "log_end_line": end_line,
                    }
                    failed = True
                update_step(plan, step_id, **step_fields)
                receipt["commands"].append(command_row)
                event = {"at": completed, "status": command_row["status"], "run_id": args.run_id}
                append_step_receipt(ledger, state, owner_id, step_id, event, repository)
                if failed:
                    break

        if failed:
            for command_id in command_ids:
                step_id = COMMAND_STEPS[command_id]
                step = next(row for row in plan["steps"] if row["id"] == step_id)
                if step["status"] == "PENDING":
                    blocked_at = server_now(repository).isoformat()
                    update_step(plan, step_id, status="BLOCKED", reason="Earlier allowlisted command failed",
                                completed_at=blocked_at)
                    append_step_receipt(ledger, state, owner_id, step_id,
                                        {"at": blocked_at, "status": "BLOCKED", "run_id": args.run_id}, repository)

        passed = not failed and len(receipt["commands"]) == len(command_ids)
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
        receipt["steps"] = state["plan"]["steps"]
        receipt["exit_code"] = 0 if passed else 1
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        receipt["exit_code"] = 2
    finally:
        receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return int(receipt.get("exit_code", 2))


if __name__ == "__main__":
    raise SystemExit(main())
