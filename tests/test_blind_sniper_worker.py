"""Deterministic tests for the durable worker queue protocol.

Exercises enqueue, exclusive claim, lease expiry, heartbeat renewal, bounded
retry, loop termination, cancellation, stale-lease recovery, reconciliation and
health reporting against the real local task ledger (file lock + hash chain).
No network and no background process is involved.
"""
from __future__ import annotations

import multiprocessing
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from blind_sniper_ledger import TaskLedger
from blind_sniper_worker import DurableQueue, QueueError

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def _run_queue_process(ledger_path, action, owner_id, now_iso, start_event, result_queue):
    """Independent worker process used to exercise real file-lock contention."""
    start_event.wait(timeout=10)
    queue = DurableQueue(TaskLedger(ledger_path))
    instant = datetime.fromisoformat(now_iso)
    try:
        if action == "claim":
            claim = queue.claim(
                owner_id=owner_id, lease_seconds=60, task_id="T-MULTIPROCESS", now=instant,
            )
            result_queue.put({"action": action, "owner_id": owner_id, "claim": claim})
        elif action == "enqueue":
            try:
                queue.enqueue(
                    task_id="T-MULTIPROCESS-DUP", kind="model_task",
                    payload_digest="digest-same", now=instant,
                )
                result_queue.put({"action": action, "owner_id": owner_id, "accepted": True})
            except QueueError as exc:
                result_queue.put({"action": action, "owner_id": owner_id, "accepted": False, "error": str(exc)})
        elif action == "recover_and_claim":
            recovery = queue.recover_stale(now=instant)
            claim = queue.claim(
                owner_id=owner_id, lease_seconds=60, task_id="T-MULTIPROCESS", now=instant,
            )
            result_queue.put({"action": action, "owner_id": owner_id, "recovery": recovery, "claim": claim})
        else:
            raise AssertionError(f"Unsupported queue process action: {action}")
    except Exception as exc:
        result_queue.put({"action": action, "owner_id": owner_id, "error": f"{type(exc).__name__}: {exc}"})


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

    def test_claim_can_target_a_specific_task_without_claiming_older_work(self):
        self.queue.enqueue(task_id="T-OLDER", kind="model_task", payload_digest="d1", now=T0)
        self.queue.enqueue(task_id="T-TARGET", kind="model_task", payload_digest="d2", now=T0)
        claim = self.queue.claim(owner_id="w1", lease_seconds=60, task_id="T-TARGET", now=T0)
        self.assertEqual(claim["task_id"], "T-TARGET")
        self.assertEqual(self.queue.status("T-OLDER")["status"], "PENDING")
        self.assertEqual(self.queue.status("T-TARGET")["status"], "CLAIMED")

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

    def test_tool_call_receipts_are_reserved_before_execution_and_bound_to_lease(self):
        self.queue.enqueue(task_id="T-TOOL", kind="model_task", payload_digest="d-tool", now=T0)
        self.queue.claim(owner_id="w-tool", lease_seconds=60, task_id="T-TOOL", now=T0)
        started = self.queue.reserve_tool_call(
            task_id="T-TOOL", owner_id="w-tool", run_id="run-1",
            tool_call_id="call-1", tool_name="repo.read_file",
            arguments_digest="args-digest", now=T0 + timedelta(seconds=1),
        )
        self.assertEqual(started["event_type"], "QUEUE_TOOL_STARTED")
        with self.assertRaisesRegex(QueueError, "already reserved"):
            self.queue.reserve_tool_call(
                task_id="T-TOOL", owner_id="w-tool", run_id="run-1",
                tool_call_id="call-1", tool_name="repo.read_file",
                arguments_digest="args-digest", now=T0 + timedelta(seconds=2),
            )
        completed = self.queue.complete_tool_call(
            task_id="T-TOOL", owner_id="w-tool", run_id="run-1",
            tool_call_id="call-1", result_digest="result-digest",
            now=T0 + timedelta(seconds=3),
        )
        self.assertEqual(completed["event_type"], "QUEUE_TOOL_COMPLETED")
        events = self.ledger.events("T-TOOL")
        self.assertEqual(
            [row["event_type"] for row in events if row["event_type"].startswith("QUEUE_TOOL_")],
            ["QUEUE_TOOL_STARTED", "QUEUE_TOOL_COMPLETED"],
        )

    def test_expired_lease_cannot_complete_or_fail(self):
        self.queue.enqueue(task_id="T-EXPIRED", kind="model_task", payload_digest="d1", now=T0)
        self.queue.claim(owner_id="w1", lease_seconds=60, now=T0)
        expired_at = T0 + timedelta(seconds=61)
        with self.assertRaisesRegex(QueueError, "lease has expired"):
            self.queue.complete(
                task_id="T-EXPIRED", owner_id="w1", result_digest="result", now=expired_at,
            )
        with self.assertRaisesRegex(QueueError, "lease has expired"):
            self.queue.fail(
                task_id="T-EXPIRED", owner_id="w1", error="late failure", now=expired_at,
            )
        self.assertEqual(self.queue.status("T-EXPIRED")["status"], "CLAIMED")
        recovery = self.queue.recover_stale(now=expired_at)
        self.assertEqual(recovery["recovered"], ["T-EXPIRED"])
        self.assertEqual(self.queue.status("T-EXPIRED")["status"], "PENDING")

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

    def _run_processes(self, actions):
        context = multiprocessing.get_context("spawn")
        start_event = context.Event()
        result_queue = context.Queue()
        processes = [
            context.Process(
                target=_run_queue_process,
                args=(str(self.ledger.path), action, owner, now.isoformat(), start_event, result_queue),
            )
            for action, owner, now in actions
        ]
        for process in processes:
            process.start()
        start_event.set()
        results = [result_queue.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(timeout=15)
            self.assertFalse(process.is_alive(), "queue worker process did not exit")
            self.assertEqual(process.exitcode, 0)
        return results

    def test_two_independent_processes_contend_for_one_task_exactly_once(self):
        self.queue.enqueue(task_id="T-MULTIPROCESS", kind="model_task", payload_digest="digest-mp", now=T0)
        results = self._run_processes([
            ("claim", "process-a", T0),
            ("claim", "process-b", T0),
        ])
        self.assertFalse([item for item in results if "error" in item], results)
        winners = [item for item in results if item.get("claim") is not None]
        losers = [item for item in results if item.get("claim") is None]
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(len(losers), 1, results)
        state = self.queue.status("T-MULTIPROCESS")
        self.assertEqual(state["status"], "CLAIMED")
        self.assertEqual(state["owner_id"], winners[0]["owner_id"])
        self.assertEqual(state["attempt"], 1)

    def test_interrupted_worker_is_recovered_by_new_process_and_stale_completion_refused(self):
        self.queue.enqueue(task_id="T-MULTIPROCESS", kind="model_task", payload_digest="digest-mp", now=T0)
        first = self._run_processes([("claim", "interrupted-worker", T0)])[0]
        self.assertIsNotNone(first.get("claim"), first)
        recovered_at = T0 + timedelta(seconds=120)
        replacement = self._run_processes([("recover_and_claim", "replacement-worker", recovered_at)])[0]
        self.assertEqual(replacement["recovery"]["recovered"], ["T-MULTIPROCESS"])
        self.assertEqual(replacement["claim"]["attempt"], 2)
        self.assertEqual(replacement["claim"]["owner_id"], "replacement-worker")
        with self.assertRaisesRegex(QueueError, "active lease"):
            self.queue.complete(
                task_id="T-MULTIPROCESS", owner_id="interrupted-worker",
                result_digest="stale-result", now=recovered_at + timedelta(seconds=1),
            )
        self.assertEqual(self.queue.status("T-MULTIPROCESS")["owner_id"], "replacement-worker")

    def test_duplicate_enqueue_race_across_independent_processes_is_refused(self):
        results = self._run_processes([
            ("enqueue", "enqueue-a", T0),
            ("enqueue", "enqueue-b", T0),
        ])
        self.assertEqual(sum(1 for item in results if item.get("accepted")), 1, results)
        rejected = [item for item in results if item.get("accepted") is False]
        self.assertEqual(len(rejected), 1, results)
        self.assertIn("already enqueued", rejected[0].get("error", ""))
        self.assertEqual(len(self.ledger.events("T-MULTIPROCESS-DUP")), 1)

    def test_queue_state_survives_reopening_the_ledger(self):
        self.queue.enqueue(task_id="T1", kind="k", payload_digest="d1", now=T0)
        reopened = DurableQueue(TaskLedger(Path(self.tmp.name) / "queue.jsonl"))
        self.assertEqual(reopened.status("T1")["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
