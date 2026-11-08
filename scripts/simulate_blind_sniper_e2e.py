#!/usr/bin/env python3
"""Deterministic end-to-end simulation of the Blind Sniper task lifecycle.

This is a CI simulation, not a real agent dispatch. It exercises the actual
runtime CLI and local ledger, injects a stale checkpoint to model interruption,
recovers from the ledger, verifies a generated artifact, and closes with a
simulation-only reviewer receipt.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CLI = ROOT / "scripts" / "blind_sniper_runtime.py"
sys.path.insert(0, str(ROOT / "scripts"))
from blind_sniper_ledger import TaskLedger  # noqa: E402


class SimulationFailure(RuntimeError):
    """The deterministic lifecycle simulation failed an acceptance check."""


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


def run_cli(args: list[str], records: list[dict[str, Any]], cwd: Path) -> None:
    command = [sys.executable, str(RUNTIME_CLI), *args]
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    records.append({
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    })
    if completed.returncode != 0:
        raise SimulationFailure(
            f"Runtime command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
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
        evidence_file = work / "evidence.json"
        result_file = work / "execution-result.md"
        recovered_file = work / "recovered-state.json"

        write_json(task_file, {
            "task_id": task_id,
            "objective": "Run a deterministic local simulation, verify its artifact, and recover after an injected interruption.",
            "workflow": "task-control-loop",
            "requested_actions": ["read", "write_file", "run_tests"],
            "repository": "madnessgate44-debug/Blind-sniper-",
            "base_commit": commit_sha,
        })

        run_cli(["plan", "--task-file", str(task_file), "--output", str(state_file),
                 "--ledger", str(ledger_file)], commands, ROOT)

        def transition(target: str, evidence: dict[str, Any] | None = None) -> None:
            extra: list[str] = []
            if evidence is not None:
                write_json(evidence_file, evidence)
                extra = ["--evidence-file", str(evidence_file)]
            run_cli(["transition", "--state-file", str(state_file), "--to", target,
                     "--output", str(state_file), "--ledger", str(ledger_file), *extra],
                    commands, ROOT)

        for target in ("INSPECTING", "SPECIFIED", "PLANNED", "EXECUTING"):
            transition(target)

        # This is the only simulated execution: create a deterministic local artifact.
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
        if not result_file.is_file() or sha256_file(result_file) != artifact_sha:
            raise SimulationFailure("Execution artifact failed SHA-256 verification.")

        transition("VERIFYING", {
            "verification_passed": True,
            "verification_kind": "deterministic_artifact_check",
            "artifact_sha256": artifact_sha,
            "commit_sha": commit_sha,
            "workflow_run_id": workflow_run_id,
        })

        # Model interruption after ledger append while the convenience checkpoint is stale.
        write_json(state_file, {"task_id": task_id, "status": "EXECUTING", "simulated_stale_checkpoint": True})
        run_cli(["recover", "--task-id", task_id, "--ledger", str(ledger_file),
                 "--output", str(recovered_file)], commands, ROOT)
        recovered = read_json(recovered_file)
        if recovered.get("status") != "VERIFYING":
            raise SimulationFailure(f"Recovery returned {recovered.get('status')!r}, expected VERIFYING.")
        shutil.copy2(recovered_file, state_file)

        transition("REVIEWING", {
            "verification_passed": True,
            "artifact_sha256": artifact_sha,
            "recovered_after_interruption": True,
        })
        transition("CLOSED", {
            "review_verdict": "PASS",
            "reviewer_id": "blind-sniper-e2e-simulation-verifier",
            "reviewer_kind": "deterministic_test_harness_not_human_or_model_agent",
            "task_id": task_id,
            "commit_sha": commit_sha,
            "ci_run_id": workflow_run_id,
            "artifact_sha256": artifact_sha,
        })

        final_state = read_json(state_file)
        history = TaskLedger(ledger_file).task_history(task_id)
        expected_states = [
            "REQUESTED", "INSPECTING", "SPECIFIED", "PLANNED",
            "EXECUTING", "VERIFYING", "REVIEWING", "CLOSED",
        ]
        actual_states = [event["payload"]["state"]["status"] for event in history["events"]]
        if final_state.get("status") != "CLOSED" or actual_states != expected_states:
            raise SimulationFailure(f"Lifecycle mismatch: final={final_state.get('status')}, states={actual_states}")
        if history["event_count"] != len(expected_states):
            raise SimulationFailure(f"Expected {len(expected_states)} ledger events, got {history['event_count']}.")

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
            "ledger_event_count": history["event_count"],
            "ledger_final_hash": history["last_event"]["event_hash"],
            "artifact_sha256": artifact_sha,
            "commit_sha": commit_sha,
            "workflow_run_id": workflow_run_id,
            "reviewer_kind": "deterministic_test_harness_not_human_or_model_agent",
        }
        write_json(output_dir / "receipt.json", receipt)
        write_json(output_dir / "commands.json", {"commands": commands})
        write_json(output_dir / "final-state.json", final_state)
        write_json(output_dir / "ledger-history.json", history)
        shutil.copy2(result_file, output_dir / "execution-result.md")
        shutil.copy2(ledger_file, output_dir / "events.jsonl")

    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SimulationFailure, OSError, ValueError, KeyError) as exc:
        print(f"E2E SIMULATION FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
