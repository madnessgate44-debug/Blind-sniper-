from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from blind_sniper_ledger import TaskLedger
from blind_sniper_browser_dispatch import BrowserDispatchError, dispatch_browser_action


class FakeAdapter:
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def execute(self, action, step_id, *args):
        self.calls.append((action, step_id, args))
        return {
            "receipt": {
                "task_id": self.kwargs["task_id"], "run_id": self.kwargs["run_id"],
                "session_id": self.kwargs["session_id"], "step_id": step_id,
                "action": action, "exit_code": 0,
            },
            "output": "fixture output",
            "error": "",
        }


class BrowserDispatchLeaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = TaskLedger(Path(self.temp.name) / "events.jsonl")
        self.task_id = "BS-DISPATCH-001"
        self.owner_id = "runner-a"
        state = {
            "task_id": self.task_id, "status": "EXECUTING",
            "implementer_id": self.owner_id, "events": [],
        }
        self.ledger.append(
            task_id=self.task_id, event_type="TASK_CREATED",
            payload={"state": state}, idempotency_key="task-created",
        )
        self.ledger.claim_task(
            task_id=self.task_id, owner_id=self.owner_id, lease_seconds=300,
            idempotency_key="lease-claim",
        )
        FakeAdapter.calls = []

    def dispatch(self, **overrides):
        args = {
            "ledger": self.ledger, "task_id": self.task_id, "owner_id": self.owner_id,
            "run_id": "run-1", "session_id": "session-1", "step_id": "step-1",
            "action": "snapshot", "action_args": [], "state_dir": self.temp.name,
            "timeout": 20, "adapter_factory": FakeAdapter,
        }
        args.update(overrides)
        return dispatch_browser_action(**args)

    def test_valid_lease_dispatches_and_persists_correlated_receipt(self):
        result = self.dispatch()
        self.assertEqual(result["receipt"]["step_id"], "step-1")
        self.assertEqual(len(FakeAdapter.calls), 1)
        events = self.ledger.task_history(self.task_id)["events"]
        self.assertEqual([row["event_type"] for row in events[-2:]], [
            "BROWSER_ACTION_STARTED", "BROWSER_ACTION_COMPLETED",
        ])
        self.assertEqual(events[-1]["payload"]["receipt"]["run_id"], "run-1")

    def test_missing_lease_blocks_before_browser_invocation(self):
        self.ledger.release_task(
            task_id=self.task_id, owner_id=self.owner_id, idempotency_key="lease-release",
        )
        with self.assertRaises(BrowserDispatchError):
            self.dispatch()
        self.assertEqual(FakeAdapter.calls, [])

    def test_wrong_lease_owner_blocks_before_browser_invocation(self):
        with self.assertRaises(BrowserDispatchError):
            self.dispatch(owner_id="runner-b")
        self.assertEqual(FakeAdapter.calls, [])

    def test_non_executing_task_blocks(self):
        state = {
            "task_id": self.task_id, "status": "PLANNED",
            "implementer_id": self.owner_id, "events": [],
        }
        self.ledger.append(
            task_id=self.task_id, event_type="TASK_REPLANNED",
            payload={"state": state}, idempotency_key="task-planned",
        )
        with self.assertRaises(BrowserDispatchError):
            self.dispatch()
        self.assertEqual(FakeAdapter.calls, [])

    def test_expired_or_short_lease_blocks(self):
        with patch("blind_sniper_ledger.datetime") as clock:
            clock.now.return_value = datetime.now(timezone.utc) + timedelta(seconds=290)
            clock.fromisoformat = datetime.fromisoformat
            with self.assertRaises(BrowserDispatchError):
                self.dispatch(timeout=20)
        self.assertEqual(FakeAdapter.calls, [])

    def test_duplicate_step_is_not_replayed(self):
        self.dispatch()
        with self.assertRaises(BrowserDispatchError):
            self.dispatch()
        self.assertEqual(len(FakeAdapter.calls), 1)

    def test_concurrent_reservations_are_atomic(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        barrier = Barrier(2)
        payload = {
            "owner_id": self.owner_id, "run_id": "run-race",
            "session_id": "session-race", "step_id": "step-race", "action": "snapshot",
        }

        def reserve():
            barrier.wait()
            return self.ledger.reserve_browser_action_if_lease(
                task_id=self.task_id, owner_id=self.owner_id, payload=payload,
                idempotency_key="browser:run-race:session-race:step-race:started",
                min_remaining_seconds=30,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reserve) for _ in range(2)]
            results = []
            for future in futures:
                try:
                    results.append(future.result())
                except ValueError as exc:
                    results.append(exc)
        self.assertEqual(sum(isinstance(item, dict) for item in results), 1)
        self.assertEqual(sum(isinstance(item, ValueError) for item in results), 1)

    def test_interrupted_started_only_step_requires_reconciliation(self):
        self.ledger.append(
            task_id=self.task_id, event_type="BROWSER_ACTION_STARTED",
            payload={
                "owner_id": self.owner_id, "run_id": "run-1",
                "session_id": "session-1", "step_id": "step-1", "action": "snapshot",
            },
            idempotency_key="browser:run-1:session-1:step-1:started",
        )
        with self.assertRaisesRegex(BrowserDispatchError, "duplicate or interrupted replay"):
            self.dispatch()
        self.assertEqual(FakeAdapter.calls, [])


if __name__ == "__main__":
    unittest.main()
