"""File-backed queue contention and restart durability tests."""
from __future__ import annotations

import multiprocessing
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from blind_sniper_ledger import TaskLedger
from blind_sniper_worker import CLAIMED, DurableQueue, QueueError


T0 = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
TASK_ID = "CONTENDED-1"


def _process_claim(path: str, owner_id: str, barrier, results) -> None:
    """Claim from a fresh ledger object after all processes are ready."""
    queue = DurableQueue(TaskLedger(path))
    barrier.wait(timeout=15)
    try:
        results.put((owner_id, queue.claim(
            owner_id=owner_id, task_id=TASK_ID, lease_seconds=300, now=T0,
        )))
    except Exception as exc:  # surface child failures to the parent test
        results.put((owner_id, "ERROR", repr(exc)))


def _sweep_claims(path: str, owner_id: str, barrier, task_ids, results) -> None:
    """Race every task: all processes sweep the same task list from a fresh ledger object."""
    queue = DurableQueue(TaskLedger(path))
    barrier.wait(timeout=30)
    won = []
    for task_id in task_ids:
        try:
            if queue.claim(owner_id=owner_id, task_id=task_id, lease_seconds=300, now=T0):
                won.append(task_id)
        except Exception as exc:
            results.put((owner_id, "ERROR", repr(exc)))
            return
    results.put((owner_id, "OK", won))


class DurableQueueContentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "queue.jsonl"
        self.queue = DurableQueue(TaskLedger(self.path))
        self.queue.enqueue(
            task_id=TASK_ID, kind="model_task", payload_digest="digest-1", now=T0,
        )

    def _assert_single_active_claim(self, queue: DurableQueue, owner_ids: set[str]):
        state = queue.status(TASK_ID)
        self.assertIsNotNone(state)
        self.assertEqual(state["status"], "CLAIMED")
        self.assertIn(state["owner_id"], owner_ids)
        self.assertGreater(
            datetime.fromisoformat(state["lease_expires_at"]).timestamp(), T0.timestamp(),
        )
        claims = [event for event in queue.ledger.events(TASK_ID) if event["event_type"] == CLAIMED]
        self.assertEqual(len(claims), 1)

    def test_eight_threads_claim_same_task_exactly_once(self):
        count = 8
        barrier = threading.Barrier(count)
        results = [None] * count

        def claim(index: int) -> None:
            try:
                barrier.wait(timeout=15)
                results[index] = self.queue.claim(
                    owner_id=f"thread-{index}", task_id=TASK_ID,
                    lease_seconds=300, now=T0,
                )
            except Exception as exc:
                results[index] = ("ERROR", repr(exc))

        threads = [threading.Thread(target=claim, args=(index,)) for index in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        errors = [result for result in results if isinstance(result, tuple)]
        self.assertEqual(errors, [], msg=f"thread errors: {errors}")
        winners = [result for result in results if result is not None]
        self.assertEqual(len(winners), 1)
        self._assert_single_active_claim(self.queue, {f"thread-{i}" for i in range(count)})

    def test_three_processes_claim_same_task_exactly_once(self):
        context = multiprocessing.get_context("fork")
        count = 3
        barrier = context.Barrier(count)
        results = context.Queue()
        processes = [
            context.Process(
                target=_process_claim,
                args=(str(self.path), f"process-{index}", barrier, results),
            )
            for index in range(count)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=25)
        self.assertTrue(all(not process.is_alive() for process in processes))
        self.assertEqual([process.exitcode for process in processes], [0] * count)
        outcomes = [results.get(timeout=5) for _ in processes]
        errors = [outcome for outcome in outcomes if len(outcome) == 3]
        self.assertEqual(errors, [], msg=f"child errors: {errors}")
        winners = [outcome for outcome in outcomes if outcome[1] is not None]
        self.assertEqual(len(winners), 1)
        self._assert_single_active_claim(
            DurableQueue(TaskLedger(self.path)), {f"process-{i}" for i in range(count)},
        )

    def test_sustained_multi_process_sweep_claims_every_task_exactly_once(self):
        task_ids = [f"SWEEP-{i:03d}" for i in range(60)]
        for task_id in task_ids:
            self.queue.enqueue(task_id=task_id, kind="model_task", payload_digest="d", now=T0)
        context = multiprocessing.get_context("spawn")
        count = 4
        barrier = context.Barrier(count)
        results = context.Queue()
        procs = [
            context.Process(target=_sweep_claims, args=(str(self.path), f"proc-{i}", barrier, task_ids, results))
            for i in range(count)
        ]
        for proc in procs:
            proc.start()
        reports = [results.get(timeout=120) for _ in procs]
        for proc in procs:
            proc.join(timeout=30)
        self.assertEqual([r for r in reports if r[1] == "ERROR"], [])
        wins = [task_id for r in reports for task_id in r[2]]
        self.assertEqual(sorted(wins), sorted(task_ids))
        for task_id in task_ids:
            claims = [e for e in self.queue.ledger.events(task_id) if e["event_type"] == CLAIMED]
            self.assertEqual(len(claims), 1, task_id)

    def test_restart_preserves_claim_and_live_lease_blocks_other_owner(self):
        original = self.queue.claim(
            owner_id="owner-a", task_id=TASK_ID, lease_seconds=300, now=T0,
        )
        before = self.queue.status(TASK_ID)

        restarted = DurableQueue(TaskLedger(self.path))
        after = restarted.status(TASK_ID)
        self.assertEqual(after["status"], before["status"])
        self.assertEqual(after["owner_id"], before["owner_id"])
        self.assertEqual(after["lease_expires_at"], before["lease_expires_at"])
        self.assertEqual(after["owner_id"], original["owner_id"])
        self.assertIsNone(restarted.claim(
            owner_id="owner-b", task_id=TASK_ID, lease_seconds=300,
            now=T0.replace(second=30),
        ))
        self.assertEqual(restarted.status(TASK_ID), before)
        self._assert_single_active_claim(restarted, {"owner-a"})

    def test_duplicate_enqueue_of_same_task_id_is_refused(self):
        with self.assertRaises(QueueError):
            self.queue.enqueue(
                task_id=TASK_ID, kind="model_task", payload_digest="digest-duplicate", now=T0,
            )
        events = self.queue.ledger.events(TASK_ID)
        self.assertEqual(sum(event["event_type"] == "QUEUE_TASK_ENQUEUED" for event in events), 1)


if __name__ == "__main__":
    unittest.main()
