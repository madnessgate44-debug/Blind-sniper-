import sys
import json
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from blind_sniper_model_worker import AgentSpec, ModelTask, ModelWorker
from blind_sniper_redact import REDACTED, redact, redact_text


class RedactorBoundaryTests(unittest.TestCase):
    def test_redactor_stays_strict_for_free_text(self) -> None:
        # The redactor is intentionally unchanged: it still redacts the tail of
        # "task-..." ids. No identifier-specific exemption exists on this branch.
        self.assertNotEqual(redact_text("task-disallowed-path-001"), "task-disallowed-path-001")
        self.assertIn(REDACTED, redact_text("xsk-" + "a" * 24))

    def test_sk_real_tokens_redacted(self) -> None:
        token = "sk-abcdefghijklmnopqrstuvwx"
        for sample in [f"key is {token}", f"({token})", token]:
            redacted = redact_text(sample)
            self.assertNotIn(token, redacted)
            self.assertIn(REDACTED, redacted)

    def test_other_credential_shapes_redacted(self) -> None:
        gh_pat = "github_pat_" + "a" * 25
        ghp = "ghp_" + "b" * 25
        aiza = "AIza" + "c" * 35
        text = f"{gh_pat} {ghp} {aiza} password: supersecretvalue123"
        redacted = redact(text)
        for secret in (gh_pat, ghp, aiza, "supersecretvalue123"):
            self.assertNotIn(secret, redacted)


class TextToolCallParserTests(unittest.TestCase):
    ALLOW = ("repo.read_file", "repo.write_file")

    def _parse(self, content):
        from blind_sniper_model_worker import _text_tool_calls
        return _text_tool_calls(content, self.ALLOW, 0)

    def test_fenced_json_tool_call_accepted(self) -> None:
        calls = self._parse('```json\n{"name": "repo.read_file", "arguments": {"path": "a.py"}}\n```')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "repo.read_file")
        self.assertEqual(json.loads(calls[0]["function"]["arguments"]), {"path": "a.py"})

    def test_bare_json_tool_call_accepted(self) -> None:
        self.assertEqual(len(self._parse('{"name": "repo.write_file", "arguments": {"path": "a", "content": "b"}}')), 1)

    def test_rejects_unlisted_tool_extra_keys_prose_and_bad_args(self) -> None:
        for content in (
            '{"name": "shell.run", "arguments": {}}',
            '{"name": "repo.read_file", "arguments": {}, "extra": 1}',
            'Sure! {"name": "repo.read_file", "arguments": {}}',
            '{"name": "repo.read_file", "arguments": {}} thanks',
            '{"name": "repo.read_file", "arguments": {}} {"name": "repo.write_file", "arguments": {}}',
            '[{"name": "repo.read_file", "arguments": {}}]',
            '{"name": "repo.read_file", "arguments": "path"}',
            '{"name": "repo.read_file"}',
            "not json {",
            None,
            ["x"],
            "x" * 30000,
        ):
            self.assertEqual(self._parse(content), [], content if isinstance(content, str) else repr(content))

    def test_tool_call_content_length_cap(self) -> None:
        short = json.dumps({"name": "repo.read_file", "arguments": {"path": "a", "note": "short"}})
        long = json.dumps({"name": "repo.read_file", "arguments": {"path": "a", "note": "x" * 20001}})
        self.assertEqual(len(self._parse(short)), 1)
        self.assertGreater(len(long), 20000)
        self.assertEqual(self._parse(long), [])


class RequireToolUseTests(unittest.TestCase):
    def _run(self, require, receipts):
        spec = AgentSpec(
            agent_id="agent-1",
            tool_allowlist=("repo.write_file",),
            permission_profile="workspace_write",
            require_tool_use=require,
        )
        task = ModelTask(task_id="task-1", agent_id="agent-1", objective="Fix code", payload={})

        def invoker(spec=None, task=None, timeout_seconds=None):
            return {
                "run_id": "run-x",
                "output_text": "I fixed it",
                "output_digest": "sha256:abc",
                "output_excerpt": "I fixed it",
                "tool_receipts": receipts,
            }

        worker = ModelWorker(invoker, max_concurrency=1, timeout_seconds=30, max_retries=0)
        return worker.run([spec], [task])["receipts"][0]

    def test_no_op_run_fails_when_tool_use_required(self) -> None:
        out = self._run(True, [])
        self.assertEqual(out["status"], "FAIL")
        self.assertEqual(out["error"], "tool_use_required_but_no_tool_receipts")

    def test_no_op_run_passes_when_not_required_legitimate_read_only(self) -> None:
        self.assertEqual(self._run(False, [])["status"], "PASS")

    def test_required_with_passing_receipt_passes(self) -> None:
        out = self._run(True, [{"tool_name": "repo.write_file", "status": "PASS"}])
        self.assertEqual(out["status"], "PASS")

    def test_required_with_failing_receipt_still_fails(self) -> None:
        out = self._run(True, [{"tool_name": "repo.write_file", "status": "FAIL"}])
        self.assertEqual(out["status"], "FAIL")

    def test_spec_rejects_bad_require_tool_use(self) -> None:
        with self.assertRaises(Exception):
            AgentSpec(agent_id="agent-1", tool_allowlist=("repo.write_file",), require_tool_use="yes")
        with self.assertRaises(Exception):
            AgentSpec(agent_id="agent-1", tool_allowlist=(), require_tool_use=True)


class ModelWorkerReceiptGateTests(unittest.TestCase):
    def _make_spec_and_task(self) -> tuple[AgentSpec, ModelTask]:
        spec = AgentSpec(
            agent_id="agent-1",
            tool_allowlist=(),
            permission_profile="read_only",
        )
        task = ModelTask(
            task_id="task-1",
            agent_id="agent-1",
            objective="Run task",
            payload={},
        )
        return spec, task

    def test_all_passing_and_empty_receipts_pass(self) -> None:
        spec, task = self._make_spec_and_task()
        calls = 0

        def invoker(spec=None, task=None, timeout_seconds=None):
            nonlocal calls
            calls += 1
            return {
                "run_id": "run-pass",
                "output_text": "done",
                "output_digest": "sha256:abc",
                "output_excerpt": "done",
                "tool_receipts": [{"tool_name": "repo.write_file", "status": "PASS"}],
            }

        worker = ModelWorker(invoker, max_concurrency=1, timeout_seconds=30, max_retries=0)
        out = worker.run([spec], [task])
        self.assertEqual(calls, 1)
        self.assertEqual(out["receipts"][0]["status"], "PASS")
        self.assertEqual(out["passed"], 1)
        self.assertEqual(out["failed"], 0)

        def empty_invoker(spec=None, task=None, timeout_seconds=None):
            return {
                "run_id": "run-empty",
                "output_text": "ok",
                "output_digest": "sha256:def",
                "output_excerpt": "ok",
                "tool_receipts": [],
            }

        worker_empty = ModelWorker(empty_invoker, max_concurrency=1, timeout_seconds=30, max_retries=0)
        out_empty = worker_empty.run([spec], [task])
        self.assertEqual(out_empty["receipts"][0]["status"], "PASS")

    def test_failing_write_receipt_fails_closed_once(self) -> None:
        spec, task = self._make_spec_and_task()
        calls = 0
        receipts = [
            {"tool_name": "repo.write_file", "status": "FAIL"},
            {"tool_name": "verification.run", "status": "PASS"},
        ]

        def invoker(spec=None, task=None, timeout_seconds=None):
            nonlocal calls
            calls += 1
            return {
                "run_id": "run-fail",
                "output_text": "partial",
                "output_digest": "sha256:111",
                "output_excerpt": "partial",
                "tool_receipts": receipts,
            }

        worker = ModelWorker(invoker, max_concurrency=1, timeout_seconds=30, max_retries=3)
        out = worker.run([spec], [task])
        receipt = out["receipts"][0]
        self.assertEqual(calls, 1)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["attempts"], 1)
        self.assertIn("repo.write_file", receipt["error"])
        self.assertEqual(receipt["tool_receipts"], receipts)
        self.assertEqual(receipt["output_digest"], "sha256:111")
        self.assertEqual(receipt["output_excerpt"], "partial")
        self.assertEqual(receipt["output_text"], "partial")
        self.assertEqual(out["passed"], 0)
        self.assertEqual(out["failed"], 1)

    def test_failing_verification_receipt_fails(self) -> None:
        spec, task = self._make_spec_and_task()

        def invoker(spec=None, task=None, timeout_seconds=None):
            return {
                "run_id": "run-ver-fail",
                "output_text": "failed",
                "output_digest": "sha256:222",
                "output_excerpt": "failed",
                "tool_receipts": [{"tool_name": "verification.run", "status": "FAIL"}],
            }

        worker = ModelWorker(invoker, max_concurrency=1, timeout_seconds=30, max_retries=0)
        out = worker.run([spec], [task])
        self.assertEqual(out["receipts"][0]["status"], "FAIL")
        self.assertIn("verification.run", out["receipts"][0]["error"])
        self.assertEqual(out["passed"], 0)
        self.assertEqual(out["failed"], 1)


class MalformedReceiptTests(unittest.TestCase):
    SECRET_MARKER = "malformed-payload-marker-do-not-leak-0123"

    def _run(self, receipts_value, *, absent=False, retries=3):
        spec = AgentSpec(agent_id="agent-1", tool_allowlist=(), permission_profile="read_only")
        task = ModelTask(task_id="job-1", agent_id="agent-1", objective="Run task", payload={})
        calls = 0

        def invoker(spec=None, task=None, timeout_seconds=None):
            nonlocal calls
            calls += 1
            out = {
                "run_id": "run-x",
                "output_text": "done",
                "output_digest": "sha256:abc",
                "output_excerpt": "done",
            }
            if not absent:
                out["tool_receipts"] = receipts_value
            return out

        worker = ModelWorker(
            invoker, max_concurrency=1, timeout_seconds=30, max_retries=retries, backoff_seconds=0
        )
        out = worker.run([spec], [task])
        return calls, out

    def test_malformed_receipts_fail_cleanly_without_retry(self) -> None:
        cases = {
            "non_dict_entry": [self.SECRET_MARKER],
            "mixed_entries": [{"tool_name": "t", "status": "PASS"}, self.SECRET_MARKER],
            "bare_string": self.SECRET_MARKER,
            "none_container": None,
            "dict_container": {"tool_name": "t", "status": "PASS", "x": self.SECRET_MARKER},
            "tuple_container": (self.SECRET_MARKER,),
        }
        for name, value in cases.items():
            with self.subTest(case=name):
                calls, out = self._run(value)
                receipt = out["receipts"][0]
                self.assertEqual(calls, 1)
                self.assertEqual(receipt["status"], "FAIL")
                self.assertEqual(receipt["attempts"], 1)
                self.assertTrue(receipt["error"].startswith("tool_receipts_malformed"))
                self.assertEqual(receipt["tool_receipts"], [])
                self.assertEqual(out["passed"], 0)
                self.assertEqual(out["failed"], 1)
                self.assertNotIn(self.SECRET_MARKER, json.dumps(receipt, default=str))

    def test_absent_and_empty_receipts_still_pass_by_design(self) -> None:
        calls, out = self._run(None, absent=True)
        self.assertEqual(calls, 1)
        self.assertEqual(out["receipts"][0]["status"], "PASS")
        calls, out = self._run([])
        self.assertEqual(out["receipts"][0]["status"], "PASS")

    def test_dict_receipt_without_status_still_fails_closed(self) -> None:
        calls, out = self._run([{"tool_name": "repo.write_file"}])
        self.assertEqual(calls, 1)
        self.assertEqual(out["receipts"][0]["status"], "FAIL")
        self.assertIn("tool_receipts_not_passing", out["receipts"][0]["error"])


if __name__ == "__main__":
    unittest.main()


class PathAuthorizationNegativeTests(unittest.TestCase):
    """End to end: a real NativeToolRuntime refusal must surface as a FAIL task.

    Fixture-level proof only. A scripted invoker drives the real tool runtime and
    durable queue, no model is involved.
    """

    def setUp(self) -> None:
        import tempfile
        from datetime import datetime, timezone

        from blind_sniper_ledger import TaskLedger
        from blind_sniper_tool_runtime import NativeToolRuntime
        from blind_sniper_worker import DurableQueue

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "ws"
        (self.root / "src").mkdir(parents=True)
        (self.root / "src" / "ok.txt").write_text("ok\n", encoding="utf-8")
        (self.root / ".github" / "workflows").mkdir(parents=True)
        self.outside = Path(self.tmp.name) / "outside.txt"
        now = datetime.now(timezone.utc)
        self.queue = DurableQueue(TaskLedger(Path(self.tmp.name) / "ledger.jsonl"))
        self.queue.enqueue(task_id="job-neg-1", kind="native_model_agent", payload_digest="d", now=now)
        self.queue.claim(owner_id="worker-1", task_id="job-neg-1", lease_seconds=3600, now=now)
        self.task = ModelTask(
            task_id="job-neg-1", agent_id="agent-1", objective="negative", payload={}, lease_owner_id="worker-1"
        )
        self.runtime = NativeToolRuntime(self.queue, workspace_root=self.root)

    def _run_gate(self, spec: AgentSpec, name: str, arguments: dict, expect_calls: int = 1) -> dict:
        calls = 0
        self._seq = getattr(self, "_seq", 0) + 1
        call_id = f"call-neg-{self._seq}"

        def invoker(spec=None, task=None, timeout_seconds=None):
            nonlocal calls
            calls += 1
            result = self.runtime.execute(
                name=name, arguments=arguments, spec=spec, task=self.task,
                run_id="run-neg", tool_call_id=call_id,
            )
            return {
                "run_id": "run-neg",
                "output_text": "model claims success",
                "output_digest": "sha256:neg",
                "output_excerpt": "model claims success",
                "tool_receipts": [result["receipt"]],
            }

        worker = ModelWorker(invoker, max_concurrency=1, timeout_seconds=30, max_retries=3)
        out = worker.run([spec], [self.task])
        self.assertEqual(calls, expect_calls)
        return out

    def _assert_failed(self, out: dict) -> None:
        self.assertEqual(out["receipts"][0]["status"], "FAIL")
        self.assertEqual(out["passed"], 0)
        self.assertEqual(out["failed"], 1)

    def test_read_path_violations_become_failed_tasks(self) -> None:
        spec = AgentSpec(agent_id="agent-1", tool_allowlist=("repo.read_file",), allowed_paths=("src/",))
        for bad in ("../outside.txt", "/etc/passwd", "src/../../outside.txt", ".env", ".git/config", "docs/x.md", "src\\ok.txt"):
            with self.subTest(path=bad):
                self._assert_failed(self._run_gate(spec, "repo.read_file", {"path": bad}))

    def test_write_without_write_profile_fails_and_writes_nothing(self) -> None:
        spec = AgentSpec(
            agent_id="agent-1", tool_allowlist=("repo.write_file",), permission_profile="read_only",
            allowed_paths=("src/new.txt",),
        )
        # validate_spec rejects a write tool on a read_only profile before any receipt is
        # reserved. It surfaces as an invoker exception, which the worker retries
        # (max_retries=3 -> 4 calls) before failing the task. No write ever happens.
        self._assert_failed(self._run_gate(spec, "repo.write_file", {"path": "src/new.txt", "content": "x"}, expect_calls=4))
        self.assertFalse((self.root / "src" / "new.txt").exists())

    def test_write_outside_allowed_paths_and_forbidden_paths_fail(self) -> None:
        spec = AgentSpec(
            agent_id="agent-1", tool_allowlist=("repo.write_file",), permission_profile="workspace_write",
            allowed_paths=("src/new.txt", ".github/workflows/x.yml"),
        )
        for bad in ("src/other.txt", "../outside.txt", ".github/workflows/x.yml"):
            with self.subTest(path=bad):
                self._assert_failed(self._run_gate(spec, "repo.write_file", {"path": bad, "content": "x"}))
        self.assertFalse(self.outside.exists())
        self.assertFalse((self.root / "src" / "other.txt").exists())
        self.assertFalse((self.root / ".github" / "workflows" / "x.yml").exists())

    def test_symlink_escape_fails(self) -> None:
        self.outside.write_text("secret-ish\n", encoding="utf-8")
        link = self.root / "src" / "link.txt"
        try:
            link.symlink_to(self.outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        spec = AgentSpec(agent_id="agent-1", tool_allowlist=("repo.read_file",), allowed_paths=("src/",))
        out = self._run_gate(spec, "repo.read_file", {"path": "src/link.txt"})
        self._assert_failed(out)
        self.assertNotIn("secret-ish", json.dumps(out))

    def test_positive_control_allowed_read_passes(self) -> None:
        spec = AgentSpec(agent_id="agent-1", tool_allowlist=("repo.read_file",), allowed_paths=("src/",))
        out = self._run_gate(spec, "repo.read_file", {"path": "src/ok.txt"})
        self.assertEqual(out["receipts"][0]["status"], "PASS")

    def test_tool_outside_allowlist_does_not_become_pass(self) -> None:
        spec = AgentSpec(agent_id="agent-1", tool_allowlist=("repo.read_file",), allowed_paths=("src/",))

        def invoker(spec=None, task=None, timeout_seconds=None):
            self.runtime.execute(
                name="repo.write_file", arguments={"path": "src/x.txt", "content": "x"}, spec=spec,
                task=self.task, run_id="run-neg", tool_call_id="call-neg",
            )
            return {"run_id": "r", "output_text": "ok", "output_digest": "sha256:x", "output_excerpt": "ok", "tool_receipts": []}

        worker = ModelWorker(invoker, max_concurrency=1, timeout_seconds=30, max_retries=0)
        out = worker.run([spec], [self.task])
        self.assertEqual(out["passed"], 0)
        self.assertFalse((self.root / "src" / "x.txt").exists())
