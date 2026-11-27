"""Offline integration coverage for native model-agent invocations."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_ledger import TaskLedger
from blind_sniper_model_worker import AgentSpec, ModelTask, ModelWorker, NativeModelInvoker
from blind_sniper_tool_runtime import NativeToolRuntime
from blind_sniper_worker import DurableQueue


class NativeAgentInvocationTests(unittest.TestCase):
    def test_isolated_invocations_scoped_tools_refusal_and_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue = DurableQueue(TaskLedger(root / "ledger.jsonl"))
            tasks = [
                ModelTask(
                    task_id="IMPLEMENT-1", agent_id="implementer", objective="write the file",
                    payload={"context": "IMPLEMENTER_ONLY_SENTINEL"}, lease_owner_id="owner-i",
                ),
                ModelTask(
                    task_id="REVIEW-1", agent_id="reviewer", objective="review the file",
                    payload={"context": "review context"}, lease_owner_id="owner-r",
                ),
            ]
            for task in tasks:
                queue.enqueue(task_id=task.task_id, kind="native_model_agent", payload_digest=task.task_id)
                queue.claim(owner_id=task.lease_owner_id, task_id=task.task_id, lease_seconds=3600)

            runtime = NativeToolRuntime(queue, workspace_root=root)
            specs = [
                AgentSpec(
                    agent_id="implementer", permission_profile="workspace_write",
                    tool_allowlist=("repo.write_file",), allowed_paths=("output.txt",),
                ),
                AgentSpec(
                    agent_id="reviewer", tool_allowlist=("repo.read_file",),
                    allowed_paths=("output.txt",),
                ),
            ]
            recorded: list[tuple[dict, dict]] = []
            dispatched_run_ids: dict[str, str] = {}
            lock = threading.Lock()

            original_execute = runtime.execute

            def record_execute_run_id(*, name, arguments, spec, task, run_id, tool_call_id):
                dispatched_run_ids[spec.agent_id] = run_id
                return original_execute(
                    name=name, arguments=arguments, spec=spec, task=task,
                    run_id=run_id, tool_call_id=tool_call_id,
                )

            def fake_post(endpoint, body, headers, timeout_seconds):
                with lock:
                    recorded.append((json.loads(json.dumps(body)), dict(headers)))
                context = json.loads(body["messages"][1]["content"])
                if context["agent_id"] == "implementer" and len(body["messages"]) == 2:
                    return {"choices": [{"finish_reason": "tool_calls", "message": {
                        "content": None,
                        "tool_calls": [{"id": "write-output", "type": "function", "function": {
                            "name": "repo.write_file",
                            "arguments": json.dumps({"path": "output.txt", "content": "written"}),
                        }}],
                    }}]}
                if context["agent_id"] == "reviewer" and len(body["messages"]) == 2:
                    return {"choices": [{"finish_reason": "tool_calls", "message": {
                        "content": None,
                        "tool_calls": [{"id": "review-write-attempt", "type": "function", "function": {
                            "name": "repo.write_file",
                            "arguments": json.dumps({
                                "path": "output.txt", "content": "must not be written",
                            }),
                        }}],
                    }}]}
                return {"choices": [{"finish_reason": "stop", "message": {"content": "done"}}]}

            invoker = NativeModelInvoker(
                base_url="http://localhost:8080", model="offline-test-model",
                tool_runtime=runtime,
            )
            worker = ModelWorker(invoker, max_concurrency=2, max_retries=0)
            with patch.object(invoker, "_post_chat_completion", side_effect=fake_post), \
                    patch.object(runtime, "execute", side_effect=record_execute_run_id), \
                    patch("socket.socket.connect", side_effect=AssertionError("network connection attempted")):
                result = worker.run(specs, tasks)

            self.assertEqual(len(recorded), 3)  # implementer tool/final rounds and reviewer refusal
            first_requests = {}
            for body, headers in recorded:
                context = json.loads(body["messages"][1]["content"])
                agent_id = context["agent_id"]
                first_requests.setdefault(agent_id, (body, headers))
            self.assertEqual(set(first_requests), {"implementer", "reviewer"})

            implementer_body, implementer_headers = first_requests["implementer"]
            reviewer_body, reviewer_headers = first_requests["reviewer"]
            self.assertEqual(
                {tool["function"]["name"] for tool in implementer_body["tools"]},
                {"repo.write_file"},
            )
            self.assertEqual(
                {tool["function"]["name"] for tool in reviewer_body["tools"]},
                {"repo.read_file"},
            )
            self.assertNotIn("repo.write_file", {
                tool["function"]["name"] for tool in reviewer_body["tools"]
            })
            self.assertIn("IMPLEMENTER_ONLY_SENTINEL", implementer_body["messages"][1]["content"])
            self.assertNotIn("IMPLEMENTER_ONLY_SENTINEL", reviewer_body["messages"][1]["content"])

            receipts = {receipt["agent_id"]: receipt for receipt in result["receipts"]}
            self.assertNotEqual(dispatched_run_ids["implementer"], dispatched_run_ids["reviewer"])
            self.assertNotEqual(
                implementer_headers["X-Client-Request-Id"],
                reviewer_headers["X-Client-Request-Id"],
            )
            for agent_id, (_, headers) in first_requests.items():
                self.assertEqual(dispatched_run_ids[agent_id], headers["X-Client-Request-Id"])
                self.assertEqual(receipts[agent_id]["agent_id"], agent_id)
            self.assertEqual(receipts["implementer"]["run_id"], dispatched_run_ids["implementer"])
            implementer_tool_receipt = receipts["implementer"]["tool_receipts"][0]
            self.assertEqual(implementer_tool_receipt["run_id"], receipts["implementer"]["run_id"])
            self.assertTrue((root / "output.txt").is_file())
            self.assertEqual((root / "output.txt").read_text(encoding="utf-8"), "written")
            reviewer_receipt = receipts["reviewer"]
            self.assertEqual(reviewer_receipt["status"], "FAIL")
            self.assertIn("NativeToolError", reviewer_receipt["error"])
            self.assertIn("not in this agent's allowlist", reviewer_receipt["error"])
            self.assertEqual((root / "output.txt").read_text(encoding="utf-8"), "written")
            self.assertEqual(result["passed"], 1)
            self.assertEqual(result["failed"], 1)


if __name__ == "__main__":
    unittest.main()
