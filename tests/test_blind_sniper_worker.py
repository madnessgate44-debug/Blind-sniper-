"""Tests for the continuous-autonomy worker pass and health digest."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_queue as queue_mod  # noqa: E402
import blind_sniper_worker as worker  # noqa: E402
from blind_sniper_ledger import TaskLedger  # noqa: E402

BASE = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = TaskLedger(Path(self.tmp.name) / "events.jsonl")
        self.queue = queue_mod.DurableQueue(self.ledger)

    def tearDown(self):
        self.tmp.cleanup()

    def enqueue(self, task_id="BS-W-001", **kw):
        return self.queue.enqueue(task_id=task_id, payload_ref="private/ref",
                                  payload_digest="a" * 40, now=BASE, **kw)

    def test_idle_pass_when_queue_empty(self):
        result = worker.run_once(self.queue, owner_id="r1", run_nonce="n1",
                                 task_runner=lambda task: {}, now=BASE)
        self.assertEqual(result["status"], "IDLE")
        self.assertEqual(result["stale_recovered"], 0)
        self.assertEqual(result["health"]["total"], 0)

    def test_successful_pass_completes_task(self):
        self.enqueue()
        seen = {}

        def runner(task):
            seen.update(task)
            return {"answer": 42}

        result = worker.run_once(self.queue, owner_id="r1", run_nonce="n1",
                                 task_runner=runner, now=BASE)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["task_id"], "BS-W-001")
        self.assertEqual(seen["task_id"], "BS-W-001")
        self.assertEqual(self.queue.status("BS-W-001", BASE)["status"], "COMPLETED")

    def test_failing_runner_applies_backoff(self):
        self.enqueue(max_attempts=3)

        def runner(task):
            raise RuntimeError("boom")

        result = worker.run_once(self.queue, owner_id="r1", run_nonce="n1",
                                 task_runner=runner, backoff_seconds=60, now=BASE)
        self.assertEqual(result["status"], "FAILED")
        self.assertFalse(result["terminal"])
        self.assertEqual(self.queue.status("BS-W-001", BASE)["status"], "QUEUED")

    def test_pass_recovers_stale_lease_before_claiming(self):
        self.enqueue()
        self.queue.claim(task_id="BS-W-001", owner_id="dead-runner", lease_seconds=60,
                         run_nonce="old", now=BASE)
        later = BASE + timedelta(seconds=120)
        result = worker.run_once(self.queue, owner_id="r1", run_nonce="n1",
                                 task_runner=lambda task: {"ok": True}, now=later)
        self.assertEqual(result["stale_recovered"], 1)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["attempt"], 2)

    def test_health_digest_flags_stale_and_failed(self):
        self.enqueue("T1")
        self.queue.claim(task_id="T1", owner_id="r1", lease_seconds=60, run_nonce="n", now=BASE)
        later = BASE + timedelta(seconds=120)
        digest = worker.health_digest(self.queue, now=later)
        self.assertTrue(digest["needs_attention"])
        self.assertEqual(digest["stale"], 1)

    def test_next_available_respects_backoff_window(self):
        self.enqueue(max_attempts=3)
        self.queue.claim(task_id="BS-W-001", owner_id="r1", run_nonce="n", now=BASE)
        self.queue.fail(task_id="BS-W-001", owner_id="r1", error="x", backoff_seconds=60, now=BASE)
        self.assertIsNone(worker.next_available(self.queue, BASE))
        self.assertEqual(worker.next_available(self.queue, BASE + timedelta(seconds=61)), "BS-W-001")


if __name__ == "__main__":
    unittest.main()
