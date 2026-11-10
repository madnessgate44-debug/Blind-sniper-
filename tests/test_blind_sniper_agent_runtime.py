"""Tests for the native model-provider transport and durable queue integration."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_agent_runtime import dispatch_task
from blind_sniper_ledger import TaskLedger
from blind_sniper_model_worker import AgentSpec, ModelTask, ModelWorker, ModelWorkerError, NativeModelInvoker
from blind_sniper_worker import DurableQueue


class NativeModelInvokerTests(unittest.TestCase):
    def test_requires_provider_configuration(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ModelWorkerError, "not configured"):
                NativeModelInvoker.from_env()

    def test_rejects_non_https_provider_except_loopback(self):
        with self.assertRaisesRegex(ModelWorkerError, "HTTPS"):
            NativeModelInvoker(base_url="http://provider.example/v1", model="test")
        self.assertIsInstance(NativeModelInvoker(base_url="http://127.0.0.1:8080/v1", model="test"), NativeModelInvoker)

    def test_sends_fresh_isolated_context_and_returns_correlated_receipt(self):
        captured = {}
        response_body = {
            "choices": [{"message": {"content": "native answer"}, "finish_reason": "stop"}]
        }

        class Response(io.BytesIO):
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.close()

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return Response(json.dumps(response_body).encode("utf-8"))

        invoker = NativeModelInvoker(
            base_url="https://provider.example/v1", model="free-model", api_key="test-secret"
        )
        spec = AgentSpec(agent_id="researcher", permission_profile="read_only")
        task = ModelTask(task_id="TASK-1", agent_id="researcher", objective="Summarize", payload={"topic": "x"})
        with patch("blind_sniper_model_worker.urlopen", side_effect=fake_urlopen):
            result = invoker(spec=spec, task=task, timeout_seconds=17)
        self.assertEqual(captured["url"], "https://provider.example/v1/chat/completions")
        self.assertEqual(captured["timeout"], 17)
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-secret")
        self.assertEqual(len(captured["body"]["messages"]), 2)
        self.assertIn("researcher", captured["body"]["messages"][0]["content"])
        self.assertIn("TASK-1", captured["body"]["messages"][1]["content"])
        self.assertEqual(result["provider"], "openai_compatible")
        self.assertTrue(result["run_id"])
        self.assertEqual(result["output_text"], "native answer")
        self.assertNotIn("test-secret", json.dumps(result))

    def test_refuses_tool_calls_until_native_executor_is_connected(self):
        invoker = NativeModelInvoker(base_url="https://provider.example/v1", model="test")
        response_body = {"choices": [{"message": {"tool_calls": [{"id": "x"}]}, "finish_reason": "tool_calls"}]}
        class Response(io.BytesIO):
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.close()
        with patch("blind_sniper_model_worker.urlopen", return_value=Response(json.dumps(response_body).encode())):
            with self.assertRaisesRegex(ModelWorkerError, "native executor"):
                invoker(
                    spec=AgentSpec(agent_id="engineer"),
                    task=ModelTask(task_id="TASK-2", agent_id="engineer", objective="x"),
                    timeout_seconds=5,
                )

    def test_refuses_write_permission_profile_until_executor_exists(self):
        invoker = NativeModelInvoker(base_url="https://provider.example/v1", model="test")
        with self.assertRaisesRegex(ModelWorkerError, "read-only"):
            invoker(
                spec=AgentSpec(agent_id="engineer", permission_profile="workspace_write"),
                task=ModelTask(task_id="TASK-4", agent_id="engineer", objective="x"),
                timeout_seconds=5,
            )

    def test_refuses_nonempty_tool_allowlist_until_executor_exists(self):
        invoker = NativeModelInvoker(base_url="https://provider.example/v1", model="test")
        with self.assertRaisesRegex(ModelWorkerError, "tool_allowlist must be empty"):
            invoker(
                spec=AgentSpec(agent_id="engineer", tool_allowlist=("filesystem.read",)),
                task=ModelTask(task_id="TASK-3", agent_id="engineer", objective="x"),
                timeout_seconds=5,
            )


class DurableModelLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.queue = DurableQueue(TaskLedger(Path(self.tmp.name) / "events.jsonl"))
        self.spec = AgentSpec(agent_id="researcher", permission_profile="read_only")
        self.task = ModelTask(
            task_id="NATIVE-TASK-1", agent_id="researcher",
            objective="Produce a bounded research summary", payload={"topic": "native runtime"},
        )

    def test_model_run_is_claimed_and_completed_in_durable_queue(self):
        def invoker(*, spec, task, timeout_seconds):
            return {
                "run_id": "run-001", "provider": "test-provider",
                "output_digest": "result-sha", "output_excerpt": "answer",
                "output_text": "answer",
            }
        receipt = dispatch_task(
            self.queue, ModelWorker(invoker, max_retries=0), self.spec, self.task,
            owner_id="runner-1",
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["run_id"], "run-001")
        self.assertEqual(receipt["queue_status"], "COMPLETED")
        state = self.queue.status(self.task.task_id)
        self.assertEqual(state["status"], "COMPLETED")
        self.assertEqual(state["result_digest"], "result-sha")
        events = self.queue.ledger.events(self.task.task_id)
        self.assertEqual(
            [row["event_type"] for row in events],
            ["QUEUE_TASK_ENQUEUED", "QUEUE_TASK_CLAIMED", "QUEUE_TASK_HEARTBEAT",
             "QUEUE_TASK_HEARTBEAT", "QUEUE_TASK_COMPLETED"],
        )

    def test_dispatch_claims_its_own_task_when_older_work_is_pending(self):
        self.queue.enqueue(
            task_id="OLDER-PENDING", kind="native_model_agent", payload_digest="older-digest",
        )
        def invoker(*, spec, task, timeout_seconds):
            return {"run_id": "run-target", "output_digest": "target-result", "output_excerpt": "ok"}
        receipt = dispatch_task(
            self.queue, ModelWorker(invoker, max_retries=0), self.spec, self.task,
            owner_id="runner-target",
        )
        self.assertEqual(receipt["queue_status"], "COMPLETED")
        self.assertEqual(self.queue.status(self.task.task_id)["status"], "COMPLETED")
        self.assertEqual(self.queue.status("OLDER-PENDING")["status"], "PENDING")

    def test_failed_model_run_returns_task_to_pending_for_bounded_retry(self):
        def invoker(*, spec, task, timeout_seconds):
            raise RuntimeError("provider unavailable")
        receipt = dispatch_task(
            self.queue, ModelWorker(invoker, max_retries=0), self.spec, self.task,
            owner_id="runner-1",
        )
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["queue_status"], "PENDING")
        self.assertEqual(self.queue.status(self.task.task_id)["attempt"], 1)

    def test_task_id_cannot_be_replayed_with_a_different_payload(self):
        self.queue.enqueue(
            task_id=self.task.task_id, kind="native_model_agent",
            payload_digest="different-digest",
        )
        with self.assertRaisesRegex(RuntimeError, "different payload digest"):
            dispatch_task(
                self.queue, ModelWorker(lambda **kwargs: {}), self.spec, self.task,
                owner_id="runner-1",
            )

    def test_completed_task_cannot_be_invoked_again(self):
        def invoker(*, spec, task, timeout_seconds):
            return {"output_digest": "d", "output_excerpt": "ok"}
        dispatch_task(
            self.queue, ModelWorker(invoker, max_retries=0), self.spec, self.task,
            owner_id="runner-1",
        )
        with self.assertRaisesRegex(RuntimeError, "not pending"):
            dispatch_task(
                self.queue, ModelWorker(invoker, max_retries=0), self.spec, self.task,
                owner_id="runner-2",
            )


if __name__ == "__main__":
    unittest.main()
