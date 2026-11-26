"""End-to-end restart and result visibility tests for the private daemon."""
from __future__ import annotations

import json
import hashlib
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from blind_sniper_daemon import BlindSniperDaemon, PrivateTaskStore
from blind_sniper_ledger import TaskLedger
from blind_sniper_model_worker import ModelWorker
from blind_sniper_worker import DurableQueue


HOST_POLICY = {
    "permission_profile": "read_only",
    "tool_allowlist": (),
    "allowed_paths": (),
    "browser_approval_reference": "",
}


class ScriptedProvider:
    def __init__(self, *, fail: bool = False, crash: bool = False) -> None:
        self.fail = fail
        self.crash = crash
        self.calls = 0

    def invoke(self, *, spec, task, timeout_seconds):
        self.calls += 1
        if self.crash:
            raise SystemExit("simulated abrupt process exit")
        if self.fail:
            raise RuntimeError("scripted provider failure")
        return {
            "run_id": f"scripted-run-{self.calls}",
            "output_text": "recovered result",
            "output_digest": "result-digest-pass",
            "output_excerpt": "recovered result",
            "tool_receipts": [],
        }


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


class BlindSniperDaemonRecoveryE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.workspace = base / "workspace"
        self.workspace.mkdir(mode=0o700)
        state = base / "private-state"
        state.mkdir(mode=0o700)
        self.store = PrivateTaskStore(state, workspace_root=self.workspace)
        self.clock = MutableClock()
        self.ledger = TaskLedger(self.store.ledger_path)
        self.ledger.server_now = self.clock
        self.queue = DurableQueue(self.ledger)

    def _write_task(self, task_id: str, *, max_attempts: int = 3) -> None:
        task = {
            "task_id": task_id,
            "agent_id": "builder",
            "objective": "Return a local scripted result",
            "payload": {},
            "require_tool_use": False,
        }
        task_path = self.store.task_dir / f"{task_id}.json"
        task_path.write_text(json.dumps(task), encoding="utf-8")
        os.chmod(task_path, 0o600)
        self.queue.enqueue(
            task_id=task_id,
            kind="native_model_agent",
            payload_digest=hashlib.sha256(json.dumps({
                "task_id": task_id,
                "agent_id": "builder",
                "objective": "Return a local scripted result",
                "payload": {},
                "permission_profile": "read_only",
                "tool_allowlist": [],
                "allowed_paths": [],
                "browser_approval_reference": "",
            }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest(),
            max_attempts=max_attempts,
        )

    def _daemon(self, provider: ScriptedProvider, owner: str) -> BlindSniperDaemon:
        return BlindSniperDaemon(
            queue=self.queue,
            worker=ModelWorker(provider.invoke, max_retries=0),
            owner_id=owner,
            store=self.store,
            lease_seconds=60,
            max_tasks_per_cycle=10,
            host_policy=HOST_POLICY,
            allowed_agent_ids=frozenset({"builder"}),
        )

    def test_new_daemon_recovers_expired_claim_and_completes_once(self) -> None:
        task_id = "RECOVER-ON-RESTART"
        self._write_task(task_id)
        daemon_a = self._daemon(ScriptedProvider(crash=True), "daemon-a")

        with self.assertRaises(SystemExit):
            daemon_a.run_once()
        claimed = self.queue.status(task_id)
        self.assertEqual(claimed["status"], "CLAIMED")
        self.assertEqual(claimed["attempt"], 1)

        self.clock.now += timedelta(seconds=61)
        provider_b = ScriptedProvider()
        daemon_b = self._daemon(provider_b, "daemon-b")
        health = daemon_b.run_once()

        state = self.queue.status(task_id)
        completed = [
            event for event in self.ledger.events(task_id)
            if event["event_type"] == "QUEUE_TASK_COMPLETED"
        ]
        self.assertEqual(state["status"], "COMPLETED")
        self.assertEqual(state["attempt"], 2)
        self.assertEqual(provider_b.calls, 1)
        self.assertEqual(len(completed), 1)
        self.assertEqual(health["counts"]["recovered_stale_leases"], 1)

        # The daemon's returned health/summary is the user-visible result surface.
        self.assertIn(task_id, health.get("tasks", {}), health)
        self.assertEqual(health["tasks"][task_id]["status"], "COMPLETED")
        self.assertEqual(health["tasks"][task_id]["result_digest"], "result-digest-pass")

    def test_provider_failures_exhaust_attempts_without_completion(self) -> None:
        task_id = "FAIL-ALL-ATTEMPTS"
        self._write_task(task_id, max_attempts=2)
        provider = ScriptedProvider(fail=True)
        daemon = self._daemon(provider, "daemon-failing")

        for _ in range(2):
            daemon.run_once()

        state = self.queue.status(task_id)
        events = self.ledger.events(task_id)
        self.assertEqual(state["status"], "FAILED")
        self.assertEqual(state["attempt"], 2)
        self.assertEqual(provider.calls, 2)
        self.assertEqual(
            sum(event["event_type"] == "QUEUE_TASK_COMPLETED" for event in events),
            0,
        )
        self.assertEqual(
            sum(event["event_type"] == "QUEUE_TASK_FAILED" for event in events),
            1,
        )


if __name__ == "__main__":
    unittest.main()
