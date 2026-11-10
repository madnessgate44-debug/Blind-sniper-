"""Deterministic tests for the durable worker queue protocol.

Exercises enqueue, exclusive claim, lease expiry, heartbeat renewal, bounded
retry, loop termination, cancellation, stale-lease recovery, reconciliation and
health reporting against the real local task ledger (file lock + hash chain).
No network and no background process is involved.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from blind_sniper_ledger import TaskLedger
from blind_sniper_worker import DurableQueue, QueueError

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class DurableQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = TaskLedger(Path(self.tmp.name) / "queue.jsonl")
        self.queue = DurableQueue(self.ledger)

    def test_enqueue_then_claim_is_exclusive(self):
        self.queue.enqueue(task_id="T1", kind="model_task", payload_digest="d1", now=T0)
        first = self.queue.claim(owner_id="w1", lease_seconds=60, now=T0)
        self.assertEqual(first["task_id"], "T1")
        self.assertEqual(first["attempt"], 1)
        # Nothing else is claimable, and a competing worker cannot take T1.
        self.assertIsNone(self.queue.claim(owner_id="w2", lease_seconds=60, now=T0))

    def test_enqueue_is_idempotent_and_rejects_duplicates(self):
        self.queue.enqueue(task_id="T1", kind="model_task", payload_digest="d1", now=T0)
        with self.assertRaises(QueueError):
            self.queue.enqueue(task_id="T1", kind="model_task", payload_digest="d1", now=T0)

    def test_heartbeat_extends_lease_and_blocks_expiry(self):
        self.queue.enqueue(task_id="T1", kind="model_task", payload_digest="d1", now=T0)
        self.queue.claim(owner_id="w1", lease_seconds=60, now=T0)
        self.queue.heartbeat(task_id="T1", owner_id="w1", lease_seconds=60, now=T0 + timedelta(seconds=50))
        # At T0+100 the original lease would be dead, but the heartbeat kept it alive.
        self.assertIsNone(self.queue.claim(owner_id="w2", lease_seconds=60, now=T0 + timedelta(seconds=100)))
        state = self.queue.status("T1")
        self.assertEqual(state["status"], "CLAIMED")

    def test_heartbeat_requires_current_owner(self):
        self.queue.enqueue(task_id="T1", kind="model_task", payload_digest="d1", now=T0)
        self.queue.claim(owner_id="w1", lease_seconds=60, now=T0)
        with self.assertRaises(QueueError):
            self.queue.heartbeat(task_id="T1", owner_id="w2", lease_seconds=60, now=T0)

    def test_stale_lease_is_recovered_and_reclaimable(self):
        self.queue.enqueue(task_id="T1", kind="model_task", payload_digest="d1", max_attempts=3, now=T0)
        self.queue.claim(owner_id="w1", lease_seconds=60, now=T0)
        later = T0 + timedelta(seconds=120)
        self.assertTrue(self.queue.health(now=later)["stale_claims"] == ["T1"])
        result = self.queue.recover_stale(now=later)
        self.assertEqual(result["recovered"], ["T1"])
        state = self.queue.status("T1")
        self.assertEqual(state["status"], "PENDING")
        self.assertEqual(state["recoveries"], 1)
        reclaimed = self.queue.claim(owner_id="w2", lease_seconds=60, now=later)
        self.assertEqual(reclaimed["task_id"], "T1")
        self.assertEqual(reclaimed["attempt"], 2)

    def test_failure_requeues_until_attempts_exhausted(self):
        self.queue.enqueue(task_id="T1", kind="model_task", payload_digest="d1", max_attempts=2, now=T0)
        claim = self.queue.claim(owner_id="w1", lease_seconds=60, now=T0)
        self.queue.fail(task_id="T1", owner_id="w1", error="boom", now=T0)
        self.assertEqual(self.queue.status("T1")["status"], "PENDING")
        claim2 = self.queue.claim(owner_id="w1", lease_seconds=60, now=T0)
        self.assertEqual(claim2["attempt"], 2)
        self.queue.fail(task_id="T1", owner_id="w1", error="boom again", now=T0)
        state = self.queue.status("T1")
        self.assertEqual(state["status"], "FAILED")
        self.assertEqual(state["attempt"], 2)
        # Exhausted tasks are never claimable again.
        self.assertIsNone(self.queue.claim(owner_id="w1", lease_seconds=60, now=T0))

    def test_exhausted_stale_lease_is_failed_not_recovered(self):
        self.queue.enqueue(task_id="T1", kind="model_task", payload_digest="d1", max_attempts=1, now=T0)
        self.queue.claim(owner_id="w1", lease_seconds=60, now=T0)
        later = T0 + timedelta(seconds=120)
        result = self.queue.recover_stale(now=later)
        self.assertEqual(result["failed"], ["T1"])
        self.assertEqual(self.queue.status("T1")["status"], "FAILED")

    def test_complete_requires_owner_and_is_terminal(self):
        self.queue.enqueue(task_id="T1", kind="model_task", payload_digest="d1", now=T0)
        self.queue.claim(owner_id="w1", lease_seconds=60, now=T0)
        with self.assertRaises(QueueError):
            self.queue.complete(task_id="T1", owner_id="w2", result_digest="r", now=T0)
        self.queue.complete(task_id="T1", owner_id="w1", result_digest="r", now=T0)
        self.assertEqual(self.queue.status("T1")["status"], "COMPLETED")
        self.assertIsNone(self.queue.claim(owner_id="w3", lease_seconds=60, now=T0))

    def test_cancel_prevents_claim(self):
        self.queue.enqueue(task_id="T1", kind="model_task", payload_digest="d1", now=T0)
        self.queue.cancel(task_id="T1", reason="owner request", now=T0)
        self.assertEqual(self.queue.status("T1")["status"], "CANCELLED")
        self.assertIsNone(self.queue.claim(owner_id="w1", lease_seconds=60, now=T0))

    def test_reconcile_and_health_report_stale_claims(self):
        self.queue.enqueue(task_id="T1", kind="model_task", payload_digest="d1", now=T0)
        self.queue.enqueue(task_id="T2", kind="model_task", payload_digest="d2", now=T0)
        self.queue.claim(owner_id="w1", lease_seconds=60, now=T0)
        later = T0 + timedelta(seconds=120)
        health = self.queue.health(now=later)
        self.assertFalse(health["healthy"])
        report = self.queue.reconcile(now=later)
        self.assertTrue(report["requires_recovery"])
        self.assertEqual(set(report["stale_claims"]), {"T1"})

    def test_claim_prefers_oldest_enqueued_task(self):
        self.queue.enqueue(task_id="T1", kind="k", payload_digest="d1", now=T0)
        self.queue.enqueue(task_id="T2", kind="k", payload_digest="d2", now=T0 + timedelta(seconds=1))
        first = self.queue.claim(owner_id="w1", lease_seconds=60, now=T0 + timedelta(seconds=2))
        self.assertEqual(first["task_id"], "T1")

    def test_queue_state_survives_reopening_the_ledger(self):
        self.queue.enqueue(task_id="T1", kind="k", payload_digest="d1", now=T0)
        reopened = DurableQueue(TaskLedger(Path(self.tmp.name) / "queue.jsonl"))
        self.assertEqual(reopened.status("T1")["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
