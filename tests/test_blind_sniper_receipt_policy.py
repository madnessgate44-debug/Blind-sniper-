from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from blind_sniper_ledger import TaskLedger
from blind_sniper_model_worker import AgentSpec, ModelTask, ModelWorker
from blind_sniper_tool_runtime import NativeToolRuntime
from blind_sniper_worker import DurableQueue


class ReceiptPolicyTests(unittest.TestCase):
    def _run(self, receipts: list[dict], *, require_tool_use: bool = True) -> dict:
        spec = AgentSpec(
            agent_id="agent-1",
            tool_allowlist=("repo.read_file", "repo.write_file", "verification.run"),
            permission_profile="workspace_write",
            require_tool_use=require_tool_use,
        )
        task = ModelTask(task_id="task-1", agent_id="agent-1", objective="Fix code", payload={})

        def invoker(spec=None, task=None, timeout_seconds=None):
            return {
                "run_id": "run-receipts",
                "output_text": "done",
                "output_digest": "sha256:abc",
                "output_excerpt": "done",
                "tool_receipts": receipts,
            }

        worker = ModelWorker(invoker, max_concurrency=1, timeout_seconds=30, max_retries=0)
        return worker.run([spec], [task])["receipts"][0]

    @staticmethod
    def _receipt(tool: str, status: str, failure_kind: str | None = None) -> dict:
        receipt = {"tool_name": tool, "status": status}
        if failure_kind is not None:
            receipt["failure_kind"] = failure_kind
        return receipt

    def test_red_verification_then_write_then_green_passes_and_keeps_trace(self) -> None:
        receipts = [
            self._receipt("repo.read_file", "PASS"),
            self._receipt("verification.run", "FAIL", "verification_failed"),
            self._receipt("repo.write_file", "PASS"),
            self._receipt("verification.run", "PASS"),
        ]
        out = self._run(receipts)
        self.assertEqual(out["status"], "PASS")
        self.assertEqual(out["tool_receipts"], receipts)

    def test_red_then_non_write_mutation_then_green_fails(self) -> None:
        out = self._run([
            self._receipt("verification.run", "FAIL", "verification_failed"),
            self._receipt("agent.handoff", "PASS"),
            self._receipt("verification.run", "PASS"),
        ])
        self.assertEqual(out["status"], "FAIL")

    def test_red_then_green_without_write_fails(self) -> None:
        self.assertEqual(self._run([
            self._receipt("verification.run", "FAIL", "verification_failed"),
            self._receipt("verification.run", "PASS"),
        ])["status"], "FAIL")

    def test_write_after_green_makes_red_verification_fail(self) -> None:
        self.assertEqual(self._run([
            self._receipt("verification.run", "FAIL", "verification_failed"),
            self._receipt("repo.write_file", "PASS"),
            self._receipt("verification.run", "PASS"),
            self._receipt("repo.write_file", "PASS"),
        ])["status"], "FAIL")

    def test_failed_write_is_never_forgiven(self) -> None:
        self.assertEqual(self._run([
            self._receipt("verification.run", "FAIL", "verification_failed"),
            self._receipt("repo.write_file", "FAIL", "tool_error"),
            self._receipt("repo.write_file", "PASS"),
            self._receipt("verification.run", "PASS"),
        ])["status"], "FAIL")

    def test_second_red_requires_its_own_later_write(self) -> None:
        self.assertEqual(self._run([
            self._receipt("verification.run", "FAIL", "verification_failed"),
            self._receipt("repo.write_file", "PASS"),
            self._receipt("verification.run", "FAIL", "verification_failed"),
            self._receipt("repo.write_file", "PASS"),
            self._receipt("verification.run", "PASS"),
        ])["status"], "PASS")

    def test_verification_tool_error_is_never_forgiven(self) -> None:
        self.assertEqual(self._run([
            self._receipt("verification.run", "FAIL", "tool_error"),
            self._receipt("repo.write_file", "PASS"),
            self._receipt("verification.run", "PASS"),
        ])["status"], "FAIL")

    def test_legacy_verification_failure_without_kind_fails_closed(self) -> None:
        self.assertEqual(self._run([
            self._receipt("verification.run", "FAIL"),
            self._receipt("repo.write_file", "PASS"),
            self._receipt("verification.run", "PASS"),
        ])["status"], "FAIL")

    def test_all_passing_receipts_pass(self) -> None:
        self.assertEqual(self._run([
            self._receipt("repo.read_file", "PASS"),
            self._receipt("repo.write_file", "PASS"),
        ])["status"], "PASS")

    def test_read_only_no_receipts_pass_when_tool_use_not_required(self) -> None:
        self.assertEqual(self._run([], require_tool_use=False)["status"], "PASS")


class NativeRuntimeReceiptPolicyTests(unittest.TestCase):
    def test_nonzero_verification_command_has_verification_failed_kind(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue = DurableQueue(TaskLedger(root / "ledger.jsonl"))
            now = datetime.now(timezone.utc)
            queue.enqueue(task_id="receipt-task", kind="native_model_agent", payload_digest="digest", now=now)
            queue.claim(owner_id="worker-1", task_id="receipt-task", lease_seconds=3600, now=now)
            task = ModelTask(
                task_id="receipt-task", agent_id="agent-1", objective="verify", payload={},
                lease_owner_id="worker-1",
            )
            runtime = NativeToolRuntime(queue, workspace_root=root)
            spec = AgentSpec(agent_id="agent-1", tool_allowlist=("verification.run",))

            class FailedCommand:
                returncode = 1
                stdout = "test failed"
                stderr = ""

            with patch("blind_sniper_tool_runtime.subprocess.run", return_value=FailedCommand()):
                result = runtime.execute(
                    name="verification.run", arguments={"command_id": "runtime-validator"},
                    spec=spec, task=task, run_id="run-1", tool_call_id="call-1",
                )

        self.assertFalse(result["ok"])
        self.assertEqual(result["receipt"]["status"], "FAIL")
        self.assertEqual(result["receipt"]["failure_kind"], "verification_failed")


if __name__ == "__main__":
    unittest.main()
