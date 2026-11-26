"""End-to-end intake gate tests for the private daemon cycle."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from blind_sniper_daemon import BlindSniperDaemon, PrivateTaskStore
from blind_sniper_ledger import TaskLedger
from blind_sniper_model_worker import ModelWorker
from blind_sniper_worker import DurableQueue


class ScriptedProvider:
    """Return a fixed model result without making a network request."""

    def __init__(self, tool_receipts: list[dict]) -> None:
        self.tool_receipts = tool_receipts
        self.calls = 0

    def invoke(self, *, spec, task, timeout_seconds):
        self.calls += 1
        return {
            "run_id": f"scripted-run-{self.calls}",
            "output_text": "scripted result",
            "output_digest": f"digest-{self.calls}",
            "output_excerpt": "scripted result",
            "tool_receipts": self.tool_receipts,
        }


class DaemonIntakeGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        workspace = base / "workspace"
        workspace.mkdir(mode=0o700)
        state = base / "private-state"
        state.mkdir(mode=0o700)
        self.store = PrivateTaskStore(state, workspace_root=workspace)
        self.queue = DurableQueue(TaskLedger(self.store.ledger_path))

    def _run_intake(self, task_id: str, receipts: list[dict], *, require_tool_use: bool = True) -> tuple[dict, dict]:
        provider = ScriptedProvider(receipts)
        worker = ModelWorker(provider.invoke, max_retries=0)
        daemon = BlindSniperDaemon(
            queue=self.queue,
            worker=worker,
            owner_id="intake-test-worker",
            store=self.store,
            lease_seconds=120,
            max_tasks_per_cycle=10,
            host_policy={
                "permission_profile": "workspace_write",
                "tool_allowlist": ("repo.read_file", "repo.write_file", "verification.run"),
                "allowed_paths": ("src/example.py",),
                "browser_approval_reference": "",
            },
            allowed_agent_ids=frozenset({"builder"}),
        )
        task = {
            "task_id": task_id,
            "agent_id": "builder",
            "objective": "Fix the code in src/example.py",
            "payload": {"target": "src/example.py"},
            "require_tool_use": require_tool_use,
        }
        task_path = self.store.task_dir / f"{task_id}.json"
        task_path.write_text(json.dumps(task), encoding="utf-8")
        os.chmod(task_path, 0o600)

        health = None
        for _ in range(3):
            health = daemon.run_once()
            if self.queue.status(task_id)["status"] in {"COMPLETED", "FAILED"}:
                break
        self.assertIn(self.queue.status(task_id)["status"], {"COMPLETED", "FAILED"})
        self.assertGreaterEqual(provider.calls, 1)
        return health, self.queue.status(task_id)

    def test_all_passing_code_task_completes(self) -> None:
        health, state = self._run_intake("INTAKE-PASS", [
            {"tool_name": "repo.read_file", "status": "PASS"},
            {"tool_name": "repo.write_file", "status": "PASS"},
            {"tool_name": "verification.run", "status": "PASS"},
        ])

        self.assertEqual(health["counts"]["completed"], 1, health)
        self.assertEqual(state["status"], "COMPLETED")

    def test_tool_error_receipt_fails_task(self) -> None:
        health, state = self._run_intake("INTAKE-TOOL-ERROR", [
            {"tool_name": "repo.write_file", "status": "FAIL", "failure_kind": "tool_error"},
        ])

        self.assertEqual(health["counts"]["failed"], 1, health)
        self.assertEqual(state["status"], "FAILED")

    def test_empty_receipts_fail_when_tool_use_is_required(self) -> None:
        health, state = self._run_intake("INTAKE-NO-TOOLS", [])

        self.assertEqual(health["counts"]["failed"], 1, health)
        self.assertEqual(state["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
