"""Tests for the task-scoped native tool runtime and durable receipts."""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_ledger import TaskLedger
from blind_sniper_model_worker import AgentSpec, ModelTask
from blind_sniper_tool_runtime import NativeToolError, NativeToolRuntime
from blind_sniper_worker import DurableQueue, QueueError

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class NativeToolRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "sample.py").write_text("value = 1\n", encoding="utf-8")
        self.queue = DurableQueue(TaskLedger(self.root / "ledger.jsonl"))
        self.queue.enqueue(task_id="TOOL-TASK-1", kind="native_model_agent", payload_digest="task-digest", now=NOW)
        self.queue.claim(owner_id="worker-1", task_id="TOOL-TASK-1", lease_seconds=900, now=NOW)
        self.task = ModelTask(
            task_id="TOOL-TASK-1", agent_id="engineer", objective="inspect or edit",
            payload={}, lease_owner_id="worker-1",
        )
        self.runtime = NativeToolRuntime(self.queue, workspace_root=self.root)

    def test_read_file_requires_explicit_path_and_persists_correlated_receipt(self):
        spec = AgentSpec(agent_id="engineer", tool_allowlist=("repo.read_file",), allowed_paths=("src/",))
        result = self.runtime.execute(
            name="repo.read_file", arguments={"path": "src/sample.py"}, spec=spec,
            task=self.task, run_id="run-1", tool_call_id="call-1",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["content"], "value = 1\n")
        self.assertEqual(result["receipt"]["status"], "PASS")
        events = self.queue.ledger.events(self.task.task_id)
        self.assertEqual(
            [row["event_type"] for row in events if row["event_type"].startswith("QUEUE_TOOL_")],
            ["QUEUE_TOOL_STARTED", "QUEUE_TOOL_COMPLETED"],
        )

    def test_read_file_rejects_parent_traversal_and_records_failure(self):
        spec = AgentSpec(agent_id="engineer", tool_allowlist=("repo.read_file",), allowed_paths=("src/",))
        result = self.runtime.execute(
            name="repo.read_file", arguments={"path": "../outside.txt"}, spec=spec,
            task=self.task, run_id="run-1", tool_call_id="call-2",
        )
        self.assertFalse(result["ok"])
        self.assertIn("traversal", result["result"]["error"])
        self.assertEqual(result["receipt"]["status"], "FAIL")

    def test_write_file_requires_workspace_write_and_exact_path_allowlist(self):
        read_only = AgentSpec(agent_id="engineer", tool_allowlist=("repo.write_file",),
                              permission_profile="read_only", allowed_paths=("src/sample.py",))
        with self.assertRaisesRegex(NativeToolError, "workspace_write"):
            self.runtime.validate_spec(read_only)
        spec = AgentSpec(agent_id="engineer", tool_allowlist=("repo.write_file",),
                         permission_profile="workspace_write", allowed_paths=("src/sample.py",))
        result = self.runtime.execute(
            name="repo.write_file", arguments={"path": "src/sample.py", "content": "value = 2\n"},
            spec=spec, task=self.task, run_id="run-2", tool_call_id="call-3",
        )
        self.assertTrue(result["ok"])
        self.assertEqual((self.root / "src" / "sample.py").read_text(encoding="utf-8"), "value = 2\n")

    def test_write_file_rejects_policy_and_workflow_paths(self):
        spec = AgentSpec(agent_id="engineer", tool_allowlist=("repo.write_file",),
                         permission_profile="workspace_write", allowed_paths=(".github/workflows/test.yml",))
        with self.assertRaisesRegex(NativeToolError, "not writable"):
            self.runtime._workspace_path(".github/workflows/test.yml", spec, write=True)

    def test_tool_call_id_cannot_be_replayed(self):
        spec = AgentSpec(agent_id="engineer", tool_allowlist=("repo.read_file",), allowed_paths=("src/",))
        kwargs = dict(
            name="repo.read_file", arguments={"path": "src/sample.py"}, spec=spec,
            task=self.task, run_id="run-3", tool_call_id="call-4",
        )
        self.runtime.execute(**kwargs)
        with self.assertRaisesRegex(QueueError, "already reserved"):
            self.runtime.execute(**kwargs)

    def test_verification_uses_only_fixed_command_without_shell(self):
        spec = AgentSpec(agent_id="qa-verifier", tool_allowlist=("verification.run",))
        class Result:
            returncode = 0
            stdout = "tests passed"
            stderr = ""
        with patch("blind_sniper_tool_runtime.subprocess.run", return_value=Result()) as run:
            result = self.runtime.execute(
                name="verification.run", arguments={"command_id": "runtime-validator"},
                spec=spec, task=self.task, run_id="run-4", tool_call_id="call-5",
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["status"], "PASS")
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual(run.call_args.args[0][1:], ["scripts/validate_blind_sniper_runtime.py"])

    def test_unknown_tools_and_commands_fail_closed(self):
        with self.assertRaisesRegex(NativeToolError, "unregistered"):
            NativeToolRuntime.definitions(("shell.exec",))
        with self.assertRaisesRegex(NativeToolError, "fixed allowlist"):
            self.runtime._run_verification({"command_id": "python -c 'print(1)'"})
