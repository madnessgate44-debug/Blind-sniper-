"""End-to-end acceptance test: durable queue + independent model agents.

This wires the real components together over a real file-locked ledger:

  enqueue -> worker claims under a lease -> two *distinct* model agents are
  invoked with fresh context and enforced tool allowlists -> task completes ->
  health/digest receipt -> the ledger is reopened (simulating a later GitHub
  Actions run) and the same state is observed -> a crashed lease is recovered.

It is deterministic and makes no network call: the model transport is faked.
It proves the R1 (separate model agents) and R2 (durable worker) controls are
real code paths, not contracts.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_model_worker as mw  # noqa: E402
import blind_sniper_queue as queue_mod  # noqa: E402
import blind_sniper_worker as worker  # noqa: E402
from blind_sniper_ledger import TaskLedger  # noqa: E402

BASE = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class EndToEndModelAndQueueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger_path = Path(self.tmp.name) / "events.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _fake_transport(self, log):
        def transport(*, url, api_key, payload, timeout):
            log.append(payload)
            return 200, {"choices": [{"message": {"content": payload["messages"][0]["content"]}}],
                         "usage": {"total_tokens": 5}}
        return transport

    def test_queue_and_model_agents_end_to_end(self):
        ledger = TaskLedger(self.ledger_path)
        queue = queue_mod.DurableQueue(ledger)
        calls = []
        invoker = mw.ModelInvoker(api_key="k", transport=self._fake_transport(calls), sleep=lambda _s: None)

        # Two independent agent identities with different allowlists.
        engineer = mw.ModelAgent(agent_id="agent-engineer", system_prompt="You are the engineer.",
                                 allowed_tools=["terminal", "file_editor"])
        reviewer = mw.ModelAgent(agent_id="agent-reviewer", system_prompt="You are the reviewer.",
                                 allowed_tools=["read_only"])

        queue.enqueue(task_id="BS-E2E-001", payload_ref="private/e2e/1",
                      payload_digest="f" * 40, now=BASE)

        def task_runner(task):
            receipts = invoker.invoke_many(jobs=[
                {"agent": engineer, "task_id": task["task_id"],
                 "messages": [{"role": "user", "content": "implement"}], "requested_tools": ["terminal"]},
                {"agent": reviewer, "task_id": task["task_id"],
                 "messages": [{"role": "user", "content": "review"}], "requested_tools": ["read_only"]},
            ], max_concurrency=2)
            agent_ids = sorted(r["agent_id"] for r in receipts)
            return {"agent_ids": agent_ids, "statuses": [r["status"] for r in receipts]}

        result = worker.run_once(queue, owner_id="runner-1", run_nonce="run-1",
                                 task_runner=task_runner, now=BASE)
        self.assertEqual(result["status"], "COMPLETED")
        # Two distinct agent identities were really invoked, each with its own context.
        self.assertEqual(result["result"]["agent_ids"], ["agent-engineer", "agent-reviewer"])
        self.assertEqual(result["result"]["statuses"], ["PASS", "PASS"])
        self.assertEqual(len(calls), 2)
        # Fresh context: engineer prompt then reviewer prompt, never shared.
        self.assertEqual(calls[0]["messages"][0]["content"], "You are the engineer.")
        self.assertEqual(calls[1]["messages"][0]["content"], "You are the reviewer.")

    def test_state_is_visible_from_a_later_ledger_handle(self):
        queue = queue_mod.DurableQueue(TaskLedger(self.ledger_path))
        queue.enqueue(task_id="BS-E2E-002", payload_ref="private/e2e/2",
                      payload_digest="a" * 40, now=BASE)
        worker.run_once(queue, owner_id="runner-1", run_nonce="run-1",
                        task_runner=lambda task: {"ok": True}, now=BASE)

        # Simulate an independent later run reopening the same durable store.
        reopened = queue_mod.DurableQueue(TaskLedger(self.ledger_path))
        self.assertEqual(reopened.status("BS-E2E-002", BASE)["status"], "COMPLETED")
        digest = worker.health_digest(reopened, now=BASE)
        self.assertEqual(digest["counts"]["COMPLETED"], 1)

    def test_crashed_worker_lease_is_recovered_by_next_run(self):
        queue = queue_mod.DurableQueue(TaskLedger(self.ledger_path))
        queue.enqueue(task_id="BS-E2E-003", payload_ref="private/e2e/3",
                      payload_digest="a" * 40, now=BASE)
        # Runner 1 claims then "crashes" (never completes).
        queue.claim(task_id="BS-E2E-003", owner_id="runner-crash", lease_seconds=60,
                    run_nonce="run-crash", now=BASE)
        later = BASE + timedelta(seconds=120)
        result = worker.run_once(queue, owner_id="runner-2", run_nonce="run-2",
                                 task_runner=lambda task: {"recovered": True}, now=later)
        self.assertEqual(result["stale_recovered"], 1)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["attempt"], 2)

    def test_model_worker_disabled_without_key_in_e2e(self):
        queue = queue_mod.DurableQueue(TaskLedger(self.ledger_path))
        queue.enqueue(task_id="BS-E2E-004", payload_ref="private/e2e/4",
                      payload_digest="a" * 40, now=BASE)
        invoker = mw.ModelInvoker(api_key="")
        agent = mw.ModelAgent(agent_id="agent-a", system_prompt="A", allowed_tools=[])
        result = worker.run_once(
            queue, owner_id="runner-1", run_nonce="run-1",
            task_runner=lambda task: invoker.invoke(
                agent=agent, task_id=task["task_id"], messages=[{"role": "user", "content": "x"}]),
            now=BASE,
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["result"]["status"], "DISABLED")


if __name__ == "__main__":
    unittest.main()
