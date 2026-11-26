"""Interrupted-run lease recovery tests for the durable queue."""
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


class DurableQueueLeaseRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.queue = DurableQueue(TaskLedger(Path(self.tmp.name) / "queue.jsonl"))
        self.queue.enqueue(
            task_id="RECOVER-1", kind="model_task", payload_digest="digest-1", now=T0,
        )

    def test_expired_claim_is_recovered_reclaimed_and_completed_by_owner_b(self):
        self.queue.claim(owner_id="owner-a", task_id="RECOVER-1", lease_seconds=60, now=T0)
        after_expiry = T0 + timedelta(seconds=61)

        recovery = self.queue.recover_stale(now=after_expiry)
        self.assertEqual(recovery["recovered"], ["RECOVER-1"])
        claim_b = self.queue.claim(
            owner_id="owner-b", task_id="RECOVER-1", lease_seconds=60, now=after_expiry,
        )
        self.assertEqual(claim_b["owner_id"], "owner-b")
        self.assertEqual(claim_b["attempt"], 2)

        self.queue.complete(
            task_id="RECOVER-1", owner_id="owner-b", result_digest="result-1",
            now=after_expiry + timedelta(seconds=1),
        )
        self.assertEqual(self.queue.status("RECOVER-1")["status"], "COMPLETED")

    def test_previous_owner_cannot_complete_or_renew_after_reclaim(self):
        self.queue.claim(owner_id="owner-a", task_id="RECOVER-1", lease_seconds=60, now=T0)
        after_expiry = T0 + timedelta(seconds=61)
        self.queue.recover_stale(now=after_expiry)
        self.queue.claim(
            owner_id="owner-b", task_id="RECOVER-1", lease_seconds=60, now=after_expiry,
        )

        with self.assertRaises(QueueError):
            self.queue.complete(
                task_id="RECOVER-1", owner_id="owner-a", result_digest="late-result",
                now=after_expiry + timedelta(seconds=1),
            )
        with self.assertRaises(QueueError):
            self.queue.heartbeat(
                task_id="RECOVER-1", owner_id="owner-a", lease_seconds=60,
                now=after_expiry + timedelta(seconds=1),
            )
        self.assertEqual(self.queue.status("RECOVER-1")["owner_id"], "owner-b")

    def test_another_owner_cannot_claim_a_still_valid_lease(self):
        self.queue.claim(owner_id="owner-a", task_id="RECOVER-1", lease_seconds=60, now=T0)

        self.assertIsNone(self.queue.claim(
            owner_id="owner-b", task_id="RECOVER-1", lease_seconds=60,
            now=T0 + timedelta(seconds=30),
        ))
        self.assertEqual(self.queue.status("RECOVER-1")["owner_id"], "owner-a")

    def test_completed_task_is_never_reclaimed(self):
        self.queue.claim(owner_id="owner-a", task_id="RECOVER-1", lease_seconds=60, now=T0)
        self.queue.complete(
            task_id="RECOVER-1", owner_id="owner-a", result_digest="result-1",
            now=T0 + timedelta(seconds=1),
        )

        self.assertIsNone(self.queue.claim(
            owner_id="owner-b", task_id="RECOVER-1", lease_seconds=60,
            now=T0 + timedelta(hours=1),
        ))
        state = self.queue.status("RECOVER-1")
        self.assertEqual(state["status"], "COMPLETED")
        self.assertEqual(state["result_digest"], "result-1")


if __name__ == "__main__":
    unittest.main()
