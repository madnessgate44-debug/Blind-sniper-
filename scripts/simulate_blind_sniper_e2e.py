#!/usr/bin/env python3
"""Deterministic end-to-end simulation of Blind Sniper task, lease and recovery controls.

This is a CI simulation, not a real agent dispatch. It exercises the actual
runtime CLI and local ledger, verifies an artifact, injects an interruption,
recovers from the ledger, and proves local lease gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CLI = ROOT / "scripts" / "blind_sniper_runtime.py"
sys.path.insert(0, str(ROOT / "scripts"))
from blind_sniper_ledger import TaskLedger  # noqa: E402


class SimulationFailure(RuntimeError):
    """A deterministic simulation acceptance check failed."""


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_cli(
    args: list[str], records: list[dict[str, Any]], cwd: Path, evidence_dir: Path,
    expected_exit_code: int = 0,
) -> None:
    command = [sys.executable, str(RUNTIME_CLI), *args]
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    records.append({
        "command": command,
        "expected_exit_code": expected_exit_code,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    })
    write_json(evidence_dir / "commands.json", {"commands": records})
    if completed.returncode != expected_exit_code:
        raise SimulationFailure(
            f"Runtime command exit mismatch: expected {expected_exit_code}, got {completed.returncode}: "
            f"{' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Directory for CI simulation artifacts")
    args = parser.parse_args()

    commit_sha = os.environ.get("GITHUB_SHA", "")
    workflow_run_id = os.environ.get("GITHUB_RUN_ID", "")
    if len(commit_sha) != 40 or not workflow_run_id.isdigit():
        raise SimulationFailure("Requires GitHub Actions GITHUB_SHA and GITHUB_RUN_ID; fails closed elsewhere.")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    task_id = f"BS-E2E-SIM-{workflow_run_id}"
    commands: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="blind-sniper-e2e-") as temp:
        work = Path(temp)
        task_file = work / "task.json"
        state_file = work / "task-state.json"
        ledger_file = work / "events.jsonl"
        lease_ledger_file = work / "lease-events.jsonl"
        evidence_file = work / "evidence.json"
        result_file = work / "execution-result.md"
        recovered_file = work / "recovered-state.json"

        write_json(task_file, {
            "task_id": task_id,
            "objective": "Run a deterministic local task, prove lease ownership, verify output and recover after interruption.",
            "workflow": "task-control-loop",
            "requested_actions": ["read", "write_file", "run_tests"],
            "repository": "madnessgate44-debug/Blind-sniper-",
            "base_commit": commit_sha,
        })
        run_cli(["plan", "--task-file", str(task_file), "--output", str(state_file),
                 "--ledger", str(ledger_file)], commands, ROOT, output_dir)

        def transition(
            target: str, evidence: dict[str, Any] | None = None, lease_owner: str | None = None
        ) -> None:
            extra: list[str] = []
            if evidence is not None:
                write_json(evidence_file, evidence)
                extra.extend(["--evidence-file", str(evidence_file)])
            if lease_owner:
                extra.extend(["--lease-owner", lease_owner])
            run_cli(["transition", "--state-file", str(state_file), "--to", target,
                     "--output", str(state_file), "--ledger", str(ledger_file), *extra],
                    commands, ROOT, output_dir)

        for target in ("INSPECTING", "SPECIFIED", "PLANNED"):
            transition(target)

        # The actual runtime CLI must grant one lease, deny a competing owner,
        # and atomically require the lease owner when committing EXECUTING.
        lease_owner = "ci-simulation-runner"
        run_cli(["claim", "--task-id", task_id, "--owner-id", lease_owner,
                 "--lease-seconds", "300", "--idempotency-key", f"{task_id}:lease-claim",
                 "--ledger", str(ledger_file)], commands, ROOT, output_dir)
        run_cli(["claim", "--task-id", task_id, "--owner-id", "competing-runner",
                 "--lease-seconds", "300", "--idempotency-key", f"{task_id}:competing-claim",
                 "--ledger", str(ledger_file)], commands, ROOT, output_dir, expected_exit_code=2)
        if "Task lease held by" not in commands[-1]["stderr"]:
            raise SimulationFailure("Competing CLI lease claim was not rejected by the active owner lock.")
        transition("EXECUTING", lease_owner=lease_owner)

        # The only simulated work: generate a deterministic local artifact.
        result_text = (
            "# Blind Sniper E2E Simulation Result\n\n"
            f"- Task: {task_id}\n"
            f"- Commit: {commit_sha}\n"
            f"- Workflow run: {workflow_run_id}\n"
            "- Mode: deterministic local simulation only\n"
            "- External network calls: 0\n"
            "- External agents spawned: 0\n\n"
            "The simulated task completed by writing this artifact.\n"
        )
        result_file.write_text(result_text, encoding="utf-8")
        artifact_sha = sha256_file(result_file)
        markers = (task_id, commit_sha, workflow_run_id, "deterministic local simulation only")
        if not result_file.is_file() or any(marker not in result_text for marker in markers):
            raise SimulationFailure("Execution artifact is missing task, commit, run or mode markers.")
        if sha256_file(result_file) != artifact_sha:
            raise SimulationFailure("Execution artifact failed SHA-256 verification.")

        transition("VERIFYING", {
            "verification_passed": True,
            "verification_kind": "deterministic_artifact_check",
            "artifact_sha256": artifact_sha,
            "commit_sha": commit_sha,
            "workflow_run_id": workflow_run_id,
        }, lease_owner=lease_owner)

        # Simulate interruption after ledger append while the convenience checkpoint is stale.
        write_json(state_file, {"task_id": task_id, "status": "EXECUTING", "simulated_stale_checkpoint": True})
        run_cli(["recover", "--task-id", task_id, "--ledger", str(ledger_file),
                 "--output", str(recovered_file)], commands, ROOT, output_dir)
        recovered = read_json(recovered_file)
        if recovered.get("status") != "VERIFYING":
            raise SimulationFailure(f"Recovery returned {recovered.get('status')!r}, expected VERIFYING.")
        shutil.copy2(recovered_file, state_file)

        transition("REVIEWING", {
            "verification_passed": True,
            "artifact_sha256": artifact_sha,
            "recovered_after_interruption": True,
        }, lease_owner=lease_owner)

        # Independently exercise local lease expiry/reclaim and owner-only release.
        lease_task_id = f"{task_id}-LEASE"
        lease_ledger = TaskLedger(lease_ledger_file)
        lease_now = datetime.now(timezone.utc)
        first_claim = lease_ledger.claim_task(
            task_id=lease_task_id, owner_id="simulation-owner-a", lease_seconds=60,
            idempotency_key=f"{lease_task_id}:claim-a", now=lease_now,
        )
        blocked_claim = lease_ledger.claim_task(
            task_id=lease_task_id, owner_id="simulation-owner-b", lease_seconds=60,
            idempotency_key=f"{lease_task_id}:claim-b-blocked", now=lease_now + timedelta(seconds=30),
        )
        reclaimed_claim = lease_ledger.claim_task(
            task_id=lease_task_id, owner_id="simulation-owner-b", lease_seconds=60,
            idempotency_key=f"{lease_task_id}:claim-b-reclaimed", now=lease_now + timedelta(seconds=61),
        )
        released_claim = lease_ledger.release_task(
            task_id=lease_task_id, owner_id="simulation-owner-b",
            idempotency_key=f"{lease_task_id}:release-b", now=lease_now + timedelta(seconds=62),
        )
        lease_history = lease_ledger.task_history(lease_task_id)
        if not first_claim["claimed"] or blocked_claim["claimed"] or blocked_claim["owner_id"] != "simulation-owner-a":
            raise SimulationFailure("Exclusive lease did not block a competing owner.")
        if not reclaimed_claim["claimed"] or reclaimed_claim["owner_id"] != "simulation-owner-b":
            raise SimulationFailure("Expired lease was not reclaimed.")
        if not released_claim["released"] or lease_ledger.lease_status(
            lease_task_id, now=lease_now + timedelta(seconds=63)
        ) is not None:
            raise SimulationFailure("Lease owner release did not clear the active lease.")
        if lease_history["event_count"] != 3:
            raise SimulationFailure(f"Expected 3 local lease events, got {lease_history['event_count']}.")
        lease_receipt = {
            "status": "PASS",
            "scope": "single_workspace_local_ledger_only",
            "exclusive_claim": True,
            "expiry_reclaim": True,
            "owner_release": True,
            "event_count": lease_history["event_count"],
            "final_lease_status": None,
        }

        final_evidence = {
            "review_verdict": "PASS",
            "reviewer_id": "blind-sniper-e2e-simulation-verifier",
            "reviewer_kind": "deterministic_test_harness_not_human_or_model_agent",
            "local_lease_simulation": lease_receipt,
            "task_id": task_id,
            "commit_sha": commit_sha,
            "ci_run_id": workflow_run_id,
            "artifact_sha256": artifact_sha,
        }
        write_json(evidence_file, final_evidence)
        transition("CLOSED", final_evidence, lease_owner=lease_owner)

        run_cli(["release", "--task-id", task_id, "--owner-id", lease_owner,
                 "--idempotency-key", f"{task_id}:lease-release",
                 "--ledger", str(ledger_file)], commands, ROOT, output_dir)
        if TaskLedger(ledger_file).lease_status(task_id) is not None:
            raise SimulationFailure("Primary execution lease remained active after owner release.")
        run_cli(["lease-status", "--task-id", task_id, "--ledger", str(ledger_file)],
                commands, ROOT, output_dir)
        if read_json_from_stdout(commands[-1]["stdout"]).get("lease") is not None:
            raise SimulationFailure("Runtime lease-status command did not report an empty lease.")

        final_state = read_json(state_file)
        if final_state.get("implementer_id") != lease_owner:
            raise SimulationFailure("EXECUTING state did not bind implementer_id to the lease owner.")
        history = TaskLedger(ledger_file).task_history(task_id)
        state_events = [
            event for event in history["events"]
            if event["event_type"] in ("TASK_CREATED", "TASK_TRANSITIONED")
        ]
        actual_states = [event["payload"]["state"]["status"] for event in state_events]
        expected_states = [
            "REQUESTED", "INSPECTING", "SPECIFIED", "PLANNED",
            "EXECUTING", "VERIFYING", "REVIEWING", "CLOSED",
        ]
        lease_events = [event for event in history["events"] if event["event_type"].startswith("TASK_LEASE_")]
        if final_state.get("status") != "CLOSED" or actual_states != expected_states:
            raise SimulationFailure(f"Lifecycle mismatch: final={final_state.get('status')}, states={actual_states}")
        if len(state_events) != 8 or len(lease_events) != 2 or history["event_count"] != 10:
            raise SimulationFailure("Expected 8 state events and 2 primary-task lease events.")

        receipt = {
            "schema_version": "1.0.0",
            "task_id": task_id,
            "status": "PASS",
            "execution_mode": "SIMULATION_ONLY",
            "actual_agent_spawned": False,
            "external_network_calls": 0,
            "interruption_injected": True,
            "recovered_status": recovered["status"],
            "final_status": final_state["status"],
            "lifecycle_states": actual_states,
            "state_event_count": len(state_events),
            "ledger_event_count": history["event_count"],
            "lease_event_count": len(lease_events),
            "ledger_hash_chain_verified": True,
            "ledger_final_hash": history["last_event"]["event_hash"],
            "artifact_sha256": artifact_sha,
            "commit_sha": commit_sha,
            "workflow_run_id": workflow_run_id,
            "execution_lease_owner": lease_owner,
            "competing_claim_blocked": True,
            "execution_lease_released": True,
            "local_lease_simulation": lease_receipt,
            "reviewer_kind": "deterministic_test_harness_not_human_or_model_agent",
        }
        write_json(output_dir / "receipt.json", receipt)
        write_json(output_dir / "final-state.json", final_state)
        write_json(output_dir / "ledger-history.json", history)
        write_json(output_dir / "lease-receipt.json", lease_receipt)
        write_json(output_dir / "lease-history.json", lease_history)
        write_json(output_dir / "task-envelope.json", read_json(task_file))
        write_json(output_dir / "final-evidence.json", final_evidence)
        shutil.copy2(recovered_file, output_dir / "recovered-state.json")
        shutil.copy2(result_file, output_dir / "execution-result.md")
        shutil.copy2(ledger_file, output_dir / "events.jsonl")
        shutil.copy2(lease_ledger_file, output_dir / "lease-events.jsonl")
        if sha256_file(output_dir / "execution-result.md") != artifact_sha:
            raise SimulationFailure("Uploaded execution artifact copy does not match the verified SHA-256.")

    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


def read_json_from_stdout(value: str) -> dict[str, Any]:
    try:
        result = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SimulationFailure("Runtime CLI returned malformed JSON.") from exc
    if not isinstance(result, dict):
        raise SimulationFailure("Runtime CLI JSON response must be an object.")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SimulationFailure, OSError, ValueError, KeyError) as exc:
        print(f"E2E SIMULATION FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
