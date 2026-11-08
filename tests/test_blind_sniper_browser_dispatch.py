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
        with patch("blind_sniper_browser_dispatch.datetime") as clock:
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


if __name__ == "__main__":
    unittest.main()
