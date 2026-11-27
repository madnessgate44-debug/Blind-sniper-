"""Deterministic lifecycle recovery tests for interrupted Blind Sniper tasks."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from blind_sniper_ledger import TaskLedger
from blind_sniper_worker import DurableQueue, QueueError


T0 = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)

# FINDING: Case 7 is skipped: NativeToolRuntime and ModelWorker do not expose
# injected time, so the spec's prerequisite for that case is not met.


class BlindSniperLifecycleRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = TaskLedger(Path(self.tmp.name) / "queue.jsonl")
        self.queue = DurableQueue(self.ledger)

    def enqueue_and_claim(self, *, task_id="task-1", max_attempts=3):
        self.queue.enqueue(
            task_id=task_id, kind="native_model_agent", payload_digest="payload-digest",
            max_attempts=max_attempts, now=T0,
        )
        self.queue.claim(owner_id="owner-a", task_id=task_id, lease_seconds=60, now=T0)

    def reserve(self, *, task_id="task-1", owner_id="owner-a", run_id="run-a", call_id="call-a", now=None):
        return self.queue.reserve_tool_call(
            task_id=task_id, owner_id=owner_id, run_id=run_id, tool_call_id=call_id,
            tool_name="repo.write_file", arguments_digest="arguments-digest", now=now or T0,
        )

    def test_crash_mid_tool_reconciles_and_recovers_without_losing_attempt(self):
        self.enqueue_and_claim()
        self.reserve()
        after_expiry = T0 + timedelta(seconds=61)

        report = self.queue.reconcile(now=after_expiry)
        self.assertEqual(report["stale_claims"], ["task-1"])
        self.assertTrue(report["requires_recovery"])

        recovered = self.queue.recover_stale(now=after_expiry)
        self.assertEqual(recovered["recovered"], ["task-1"])
        state = self.queue.status("task-1")
        self.assertEqual(state["status"], "PENDING")
        self.assertEqual(state["attempt"], 1)
        reclaimed = self.queue.claim(
            owner_id="owner-b", task_id="task-1", lease_seconds=60, now=after_expiry,
        )
        self.assertEqual(reclaimed["attempt"], 2)

    def test_stale_owner_is_fenced_after_recovery(self):
        self.enqueue_and_claim()
        self.reserve()
        after_expiry = T0 + timedelta(seconds=61)
        self.queue.recover_stale(now=after_expiry)
        self.queue.claim(owner_id="owner-b", task_id="task-1", lease_seconds=60, now=after_expiry)

        with self.assertRaises(QueueError):
            self.queue.complete_tool_call(
                task_id="task-1", owner_id="owner-a", run_id="run-a", tool_call_id="call-a",
                result_digest="late-result", now=after_expiry + timedelta(seconds=1),
            )
        with self.assertRaises(QueueError):
            self.queue.heartbeat(
                task_id="task-1", owner_id="owner-a", lease_seconds=60,
                now=after_expiry + timedelta(seconds=1),
            )
        with self.assertRaises(QueueError):
            self.queue.complete(
                task_id="task-1", owner_id="owner-a", result_digest="late-result",
                now=after_expiry + timedelta(seconds=1),
            )

        self.reserve(
            owner_id="owner-b", run_id="run-b", call_id="call-b",
            now=after_expiry + timedelta(seconds=1),
        )
        self.queue.complete_tool_call(
            task_id="task-1", owner_id="owner-b", run_id="run-b", tool_call_id="call-b",
            result_digest="owner-b-result", now=after_expiry + timedelta(seconds=1),
        )
        self.queue.complete(
            task_id="task-1", owner_id="owner-b", result_digest="owner-b-result",
            now=after_expiry + timedelta(seconds=2),
        )
        self.assertEqual(self.queue.status("task-1")["status"], "COMPLETED")

    def test_tool_receipt_replay_is_refused_but_new_run_and_call_are_accepted(self):
        self.enqueue_and_claim()
        self.reserve()
        with self.assertRaisesRegex(QueueError, "already reserved"):
            self.reserve(now=T0 + timedelta(seconds=1))

        accepted = self.reserve(
            run_id="run-b", call_id="call-b", now=T0 + timedelta(seconds=2),
        )
        self.assertEqual(accepted["event_type"], "QUEUE_TOOL_STARTED")

    def test_exhausted_attempt_is_failed_for_lease_loss_and_never_claimable(self):
        self.enqueue_and_claim(max_attempts=1)
        after_expiry = T0 + timedelta(seconds=61)
        outcome = self.queue.recover_stale(now=after_expiry)
        self.assertEqual(outcome["failed"], ["task-1"])
        state = self.queue.status("task-1")
        self.assertEqual(state["status"], "FAILED")
        self.assertIn("lease_lost", state["last_error"])
        self.assertIsNone(self.queue.claim(
            owner_id="owner-b", task_id="task-1", lease_seconds=60, now=after_expiry,
        ))

    def test_recovery_is_idempotent_and_appends_only_one_recovered_event(self):
        self.enqueue_and_claim()
        after_expiry = T0 + timedelta(seconds=61)
        first = self.queue.recover_stale(now=after_expiry)
        second = self.queue.recover_stale(now=after_expiry)

        self.assertEqual(first["recovered"], ["task-1"])
        self.assertEqual(second, {"recovered": [], "failed": []})
        recovered_rows = [
            row for row in self.ledger.events("task-1")
            if row["event_type"] == "QUEUE_TASK_RECOVERED"
        ]
        self.assertEqual(len(recovered_rows), 1)

    def test_cancelled_task_is_not_recovered_or_reclaimed(self):
        self.enqueue_and_claim()
        self.queue.cancel(task_id="task-1", reason="owner request", now=T0 + timedelta(seconds=1))
        after_expiry = T0 + timedelta(seconds=61)

        self.assertEqual(self.queue.recover_stale(now=after_expiry), {"recovered": [], "failed": []})
        self.assertEqual(self.queue.status("task-1")["status"], "CANCELLED")
        self.assertIsNone(self.queue.claim(
            owner_id="owner-b", task_id="task-1", lease_seconds=60, now=after_expiry,
        ))


if __name__ == "__main__":
    unittest.main()
