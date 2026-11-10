"""Tests for the durable queue / claim / lease / heartbeat / recovery protocol.

These exercise the real ``TaskLedger`` (file-locked, hash-chained) and a fake
in-memory ledger used to prove first-writer-wins claim semantics under a race.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_queue as queue_mod  # noqa: E402
from blind_sniper_ledger import TaskLedger  # noqa: E402

BASE = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class DurableQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = TaskLedger(Path(self.tmp.name) / "events.jsonl")
        self.queue = queue_mod.DurableQueue(self.ledger)

    def tearDown(self):
        self.tmp.cleanup()

    def enqueue(self, task_id="BS-Q-001", **kw):
        return self.queue.enqueue(
            task_id=task_id, payload_ref="private/ref/1",
            payload_digest="a" * 40, now=BASE, **kw,
        )

    def test_enqueue_then_status_is_queued(self):
        self.enqueue()
        state = self.queue.status("BS-Q-001", BASE)
        self.assertEqual(state["status"], "QUEUED")
        self.assertEqual(state["attempts"], 0)
        self.assertFalse(state["lease_active"])

    def test_enqueue_rejects_raw_payload_and_requires_digest(self):
        with self.assertRaises(queue_mod.QueueError):
            self.queue.enqueue(task_id="T", payload_ref="r", payload_digest="short", now=BASE)

    def test_claim_sets_active_lease_and_increments_attempts(self):
        self.enqueue()
        result = self.queue.claim(task_id="BS-Q-001", owner_id="runner-a", lease_seconds=300,
                                  run_nonce="n1", now=BASE)
        self.assertTrue(result["claimed"])
        self.assertEqual(result["attempt"], 1)
        state = self.queue.status("BS-Q-001", BASE)
        self.assertEqual(state["status"], "CLAIMED")
        self.assertEqual(state["lease_owner"], "runner-a")
        self.assertTrue(state["lease_active"])

    def test_second_owner_cannot_claim_active_lease(self):
        self.enqueue()
        self.queue.claim(task_id="BS-Q-001", owner_id="runner-a", run_nonce="n1", now=BASE)
        blocked = self.queue.claim(task_id="BS-Q-001", owner_id="runner-b", run_nonce="n2", now=BASE)
        self.assertFalse(blocked["claimed"])
        self.assertEqual(blocked["owner_id"], "runner-a")

    def test_claim_race_is_first_writer_wins(self):
        # Both runners append before either re-reads; the earlier seq must win.
        self.enqueue()
        first = self.queue.claim(task_id="BS-Q-001", owner_id="runner-a", run_nonce="n1", now=BASE)
        second = self.queue.claim(task_id="BS-Q-001", owner_id="runner-b", run_nonce="n2", now=BASE)
        self.assertTrue(first["claimed"])
        self.assertFalse(second["claimed"])

    def test_heartbeat_renews_only_for_active_owner(self):
        self.enqueue()
        self.queue.claim(task_id="BS-Q-001", owner_id="runner-a", lease_seconds=60, run_nonce="n1", now=BASE)
        renewed = self.queue.heartbeat(task_id="BS-Q-001", owner_id="runner-a", lease_seconds=300,
                                       run_nonce="n1", now=BASE + timedelta(seconds=30))
        self.assertTrue(renewed["renewed"])
        wrong = self.queue.heartbeat(task_id="BS-Q-001", owner_id="runner-b", lease_seconds=300,
                                     run_nonce="n2", now=BASE + timedelta(seconds=30))
        self.assertFalse(wrong["renewed"])

    def test_lease_expiry_marks_stale_and_recovery_reclaims(self):
        self.enqueue()
        self.queue.claim(task_id="BS-Q-001", owner_id="runner-a", lease_seconds=60, run_nonce="n1", now=BASE)
        later = BASE + timedelta(seconds=120)
        self.assertTrue(self.queue.status("BS-Q-001", later)["stale"])
        recovered = self.queue.recover_stale(now=later)
        self.assertEqual(recovered["count"], 1)
        self.assertEqual(recovered["recovered"][0]["prior_owner_id"], "runner-a")
        self.assertEqual(self.queue.status("BS-Q-001", later)["status"], "QUEUED")
        # Idempotent: a second sweep finds nothing new.
        self.assertEqual(self.queue.recover_stale(now=later)["count"], 0)

    def test_recovered_task_can_be_reclaimed(self):
        self.enqueue()
        self.queue.claim(task_id="BS-Q-001", owner_id="runner-a", lease_seconds=60, run_nonce="n1", now=BASE)
        later = BASE + timedelta(seconds=120)
        self.queue.recover_stale(now=later)
        reclaim = self.queue.claim(task_id="BS-Q-001", owner_id="runner-b", run_nonce="n2", now=later)
        self.assertTrue(reclaim["claimed"])
        self.assertEqual(reclaim["attempt"], 2)

    def test_fail_with_backoff_returns_task_to_queue(self):
        self.enqueue(max_attempts=3)
        self.queue.claim(task_id="BS-Q-001", owner_id="runner-a", run_nonce="n1", now=BASE)
        failed = self.queue.fail(task_id="BS-Q-001", owner_id="runner-a", error="boom",
                                 backoff_seconds=60, now=BASE)
        self.assertTrue(failed["failed"])
        self.assertFalse(failed["terminal"])
        state = self.queue.status("BS-Q-001", BASE)
        self.assertEqual(state["status"], "QUEUED")
        # Not yet available until the backoff elapses.
        early = self.queue.claim(task_id="BS-Q-001", owner_id="runner-b", run_nonce="n2", now=BASE)
        self.assertFalse(early["claimed"])

    def test_exhausting_attempts_is_terminal_failure(self):
        self.enqueue(max_attempts=1)
        self.queue.claim(task_id="BS-Q-001", owner_id="runner-a", run_nonce="n1", now=BASE)
        failed = self.queue.fail(task_id="BS-Q-001", owner_id="runner-a", error="boom", now=BASE)
        self.assertTrue(failed["terminal"])
        self.assertEqual(self.queue.status("BS-Q-001", BASE)["status"], "FAILED")
        self.assertFalse(self.queue.claim(task_id="BS-Q-001", owner_id="runner-b", run_nonce="n2", now=BASE)["claimed"])

    def test_complete_requires_active_owner(self):
        self.enqueue()
        self.queue.claim(task_id="BS-Q-001", owner_id="runner-a", run_nonce="n1", now=BASE)
        wrong = self.queue.complete(task_id="BS-Q-001", owner_id="runner-b", receipt={}, now=BASE)
        self.assertFalse(wrong["completed"])
        done = self.queue.complete(task_id="BS-Q-001", owner_id="runner-a", receipt={"ok": True}, now=BASE)
        self.assertTrue(done["completed"])
        self.assertEqual(self.queue.status("BS-Q-001", BASE)["status"], "COMPLETED")

    def test_cancel_is_terminal_and_blocks_claim(self):
        self.enqueue()
        self.assertTrue(self.queue.cancel(task_id="BS-Q-001", reason="owner stop", now=BASE)["cancelled"])
        self.assertEqual(self.queue.status("BS-Q-001", BASE)["status"], "CANCELLED")
        self.assertFalse(self.queue.claim(task_id="BS-Q-001", owner_id="runner-a", run_nonce="n1", now=BASE)["claimed"])

    def test_health_and_reconcile_report_drift(self):
        self.enqueue()
        health = self.queue.health(now=BASE)
        self.assertEqual(health["counts"]["QUEUED"], 1)
        self.assertEqual(health["total"], 1)
        in_sync = self.queue.reconcile(expected={"BS-Q-001": "QUEUED"}, now=BASE)
        self.assertTrue(in_sync["in_sync"])
        drift = self.queue.reconcile(expected={"BS-Q-001": "COMPLETED"}, now=BASE)
        self.assertFalse(drift["in_sync"])
        self.assertEqual(drift["drift"]["BS-Q-001"]["actual"], "QUEUED")

    def test_queue_state_survives_a_new_ledger_handle(self):
        # Cross-run durability: a fresh process reopening the same ledger sees the same state.
        self.enqueue()
        self.queue.claim(task_id="BS-Q-001", owner_id="runner-a", run_nonce="n1", now=BASE)
        reopened = queue_mod.DurableQueue(TaskLedger(Path(self.tmp.name) / "events.jsonl"))
        state = reopened.status("BS-Q-001", BASE)
        self.assertEqual(state["status"], "CLAIMED")
        self.assertEqual(state["lease_owner"], "runner-a")


if __name__ == "__main__":
    unittest.main()
