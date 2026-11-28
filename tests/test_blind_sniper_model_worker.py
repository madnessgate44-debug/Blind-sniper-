"""Tests for the independent model-agent worker contract.

Uses a deterministic in-process invoker (no network, no real model). Proves
distinct agent IDs, fresh contexts, tool/permission allowlists, correlated task
IDs, bounded concurrency, per-attempt timeouts, bounded retries and one receipt
per task.
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from blind_sniper_model_worker import (
    AgentSpec,
    ModelTask,
    ModelWorker,
    ModelWorkerError,
    NativeModelInvoker,
)


def recording_invoker(record):
    def invoker(*, spec, task, timeout_seconds):
        record.append((spec.agent_id, task.task_id))
        return {"conversation_id": f"conv-{task.task_id}", "output_digest": "d", "output_excerpt": "ok"}
    return invoker


class ModelWorkerContractTests(unittest.TestCase):
    def test_rejects_non_fresh_context(self):
        with self.assertRaisesRegex(ModelWorkerError, "fresh context"):
            AgentSpec(agent_id="engineer-1", fresh_context=False)

    def test_rejects_unknown_permission_profile(self):
        with self.assertRaisesRegex(ModelWorkerError, "permission_profile"):
            AgentSpec(agent_id="engineer-1", permission_profile="god_mode")

    def test_rejects_invalid_task_id(self):
        with self.assertRaises(ModelWorkerError):
            ModelTask(task_id="bad id!", agent_id="engineer-1", objective="x")

    def test_runs_distinct_agents_with_correlated_receipts(self):
        calls = []
        worker = ModelWorker(recording_invoker(calls), max_concurrency=2)
        specs = [AgentSpec(agent_id="engineer-1"), AgentSpec(agent_id="reviewer-1")]
        tasks = [
            ModelTask(task_id="T1", agent_id="engineer-1", objective="implement"),
            ModelTask(task_id="T2", agent_id="reviewer-1", objective="review"),
        ]
        result = worker.run(specs, tasks)
        self.assertEqual(result["distinct_agents"], ["engineer-1", "reviewer-1"])
        self.assertEqual(result["passed"], 2)
        by_task = {r["task_id"]: r for r in result["receipts"]}
        self.assertEqual(by_task["T1"]["agent_id"], "engineer-1")
        self.assertEqual(by_task["T2"]["agent_id"], "reviewer-1")
        self.assertTrue(by_task["T1"]["fresh_context"])
        self.assertEqual(set(calls), {("engineer-1", "T1"), ("reviewer-1", "T2")})

    def test_unknown_agent_is_rejected(self):
        worker = ModelWorker(recording_invoker([]))
        with self.assertRaisesRegex(ModelWorkerError, "No agent spec"):
            worker.run([AgentSpec(agent_id="a")], [ModelTask(task_id="T1", agent_id="b", objective="x")])

    def test_duplicate_task_ids_are_rejected(self):
        worker = ModelWorker(recording_invoker([]))
        with self.assertRaisesRegex(ModelWorkerError, "Duplicate task_id"):
            worker.run(
                [AgentSpec(agent_id="a")],
                [ModelTask(task_id="T1", agent_id="a", objective="x"),
                 ModelTask(task_id="T1", agent_id="a", objective="y")],
            )

    def test_concurrency_never_exceeds_the_bound(self):
        active = {"now": 0, "max": 0}
        lock = threading.Lock()

        def invoker(*, spec, task, timeout_seconds):
            with lock:
                active["now"] += 1
                active["max"] = max(active["max"], active["now"])
            time.sleep(0.05)
            with lock:
                active["now"] -= 1
            return {"output_digest": "d"}

        worker = ModelWorker(invoker, max_concurrency=2)
        specs = [AgentSpec(agent_id=f"a{i}") for i in range(6)]
        tasks = [ModelTask(task_id=f"T{i}", agent_id=f"a{i}", objective="x") for i in range(6)]
        worker.run(specs, tasks)
        self.assertLessEqual(active["max"], 2)

    def test_timeout_is_bounded_and_reported(self):
        def slow(*, spec, task, timeout_seconds):
            time.sleep(2)
            return {"output_digest": "d"}

        worker = ModelWorker(slow, timeout_seconds=1, max_retries=0)
        result = worker.run([AgentSpec(agent_id="a")], [ModelTask(task_id="T1", agent_id="a", objective="x")])
        receipt = result["receipts"][0]
        self.assertEqual(receipt["status"], "FAIL")
        self.assertIn("timed out", receipt["error"])

    def test_retries_until_success(self):
        state = {"n": 0}

        def flaky(*, spec, task, timeout_seconds):
            state["n"] += 1
            if state["n"] < 3:
                raise RuntimeError("transient")
            return {"output_digest": "d"}

        worker = ModelWorker(flaky, max_retries=3)
        result = worker.run([AgentSpec(agent_id="a")], [ModelTask(task_id="T1", agent_id="a", objective="x")])
        receipt = result["receipts"][0]
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["attempts"], 3)

    def test_permanent_failure_reports_fail_with_error(self):
        def always_fail(*, spec, task, timeout_seconds):
            raise RuntimeError("permanent")

        worker = ModelWorker(always_fail, max_retries=1)
        result = worker.run([AgentSpec(agent_id="a")], [ModelTask(task_id="T1", agent_id="a", objective="x")])
        receipt = result["receipts"][0]
        self.assertEqual(receipt["status"], "FAIL")
        self.assertIn("permanent", receipt["error"])

    def test_receipt_output_excerpt_is_redacted(self):
        def leaky(*, spec, task, timeout_seconds):
            return {"output_digest": "d", "output_excerpt": "leak ghp_" + "a" * 30}

        worker = ModelWorker(leaky)
        result = worker.run([AgentSpec(agent_id="a")], [ModelTask(task_id="T1", agent_id="a", objective="x")])
        self.assertNotIn("ghp_", result["receipts"][0]["output_excerpt"])

    def test_invalid_concurrency_configuration(self):
        with self.assertRaises(ModelWorkerError):
            ModelWorker(recording_invoker([]), max_concurrency=0)

    def test_tool_limit_failure_preserves_receipts_and_digest_only_round_trace(self):
        class FakeToolRuntime:
            def validate_spec(self, spec):
                pass

            def definitions(self, allowlist):
                return [{"type": "function", "function": {"name": name, "parameters": {}}} for name in allowlist]

            def execute(self, *, name, arguments, spec, task, run_id, tool_call_id):
                return {
                    "ok": True,
                    "receipt": {
                        "tool_name": name,
                        "tool_call_id": tool_call_id,
                        "status": "PASS",
                    },
                }

        secret_args = {"path": "secrets/private_key.pem", "token": "ghp_" + "a" * 30}
        expected_digest = hashlib.sha256(
            json.dumps(secret_args, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        spec = AgentSpec(agent_id="engineer-1", tool_allowlist=("repo.read_file",))
        task = ModelTask(task_id="T-limit", agent_id="engineer-1", objective="inspect")

        cases = [
            (1, "Native model exceeded the bounded tool-round limit", [0, 1, 2, 3]),
            (3, "Native model exceeded the bounded tool-call limit", [0, 0, 0, 1, 1, 1, 2, 2]),
        ]
        for calls_per_round, expected_error, expected_rounds in cases:
            with self.subTest(calls_per_round=calls_per_round):
                counter = {"n": 0}

                def fake_post(endpoint, body, headers, timeout_seconds):
                    tool_calls = []
                    for _ in range(calls_per_round):
                        counter["n"] += 1
                        tool_calls.append({
                            "id": f"call-{counter['n']}",
                            "type": "function",
                            "function": {
                                "name": "repo.read_file",
                                "arguments": json.dumps(secret_args),
                            },
                        })
                    return {
                        "choices": [{
                            "message": {"role": "assistant", "content": None, "tool_calls": tool_calls},
                            "finish_reason": "tool_calls",
                        }]
                    }

                invoker = NativeModelInvoker(
                    base_url="https://example.invalid/v1",
                    model="fake-model",
                    tool_runtime=FakeToolRuntime(),
                )
                self.assertEqual(invoker.max_tool_rounds, 4)
                self.assertEqual(invoker.max_tool_calls, 8)
                invoker._post_chat_completion = fake_post

                worker = ModelWorker(invoker, max_retries=0)
                result = worker.run([spec], [task])
                receipt = result["receipts"][0]
                self.assertEqual(receipt["status"], "FAIL")
                self.assertEqual(receipt["error"], f"ModelWorkerError: {expected_error}")
                self.assertEqual(len(receipt["tool_receipts"]), len(expected_rounds))
                self.assertEqual(len(receipt["round_trace"]), len(expected_rounds))
                self.assertEqual([entry["round_index"] for entry in receipt["round_trace"]], expected_rounds)
                for entry in receipt["round_trace"]:
                    self.assertEqual(set(entry), {"round_index", "tool_name", "args_digest", "status"})
                    self.assertEqual(entry["tool_name"], "repo.read_file")
                    self.assertEqual(entry["args_digest"], expected_digest)
                    self.assertEqual(entry["status"], "PASS")
                serialized_trace = json.dumps(receipt["round_trace"])
                self.assertNotIn("private_key.pem", serialized_trace)
                self.assertNotIn("secrets/", serialized_trace)
                self.assertNotIn("ghp_", serialized_trace)


if __name__ == "__main__":
    unittest.main()
