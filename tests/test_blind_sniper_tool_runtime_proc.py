"""Process supervision tests for native verification commands."""
from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import blind_sniper_tool_runtime as tool_runtime


def process_is_running(pid: int) -> bool:
    """Treat a killed zombie as stopped when the container init has not reaped it."""
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        try:
            return stat.read_text(encoding="utf-8").split()[2] != "Z"
        except (OSError, IndexError):
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class QueueStub:
    def reserve_tool_call(self, *args, **kwargs):
        pass

    def complete_tool_call(self, *args, **kwargs):
        pass


class VerificationProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = tool_runtime.NativeToolRuntime(
            QueueStub(), workspace_root=self.root, command_timeout=2,
        )

    def run_python(self, source: str, *, timeout: int = 2):
        self.runtime.command_timeout = timeout
        with patch.dict(tool_runtime.COMMANDS, {
            "unit-tests": [sys.executable, "-c", source],
        }), patch.object(tool_runtime, "PROCESS_POPEN", wraps=tool_runtime.PROCESS_POPEN):
            return self.runtime._run_verification({"command_id": "unit-tests"})

    def test_timeout_kills_descendant_process_group(self):
        pid_file = self.root / "grandchild.pid"
        child = "import time; time.sleep(30)"
        parent = (
            "import signal,subprocess,sys,time; "
            f"p=subprocess.Popen([sys.executable,'-c',{child!r}]); "
            f"open({str(pid_file)!r},'w').write(str(p.pid)); "
            "signal.signal(signal.SIGTERM, lambda *_: (p.wait(), sys.exit(0))); "
            "time.sleep(30)"
        )
        result = self.run_python(parent, timeout=1)
        self.assertEqual(result["status"], "TIMED_OUT")
        self.assertIsNone(result["exit_code"])
        self.assertTrue(pid_file.exists())
        grandchild_pid = int(pid_file.read_text(encoding="utf-8"))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if not process_is_running(grandchild_pid):
                break
            time.sleep(0.02)
        else:
            self.fail(f"grandchild process {grandchild_pid} still exists after timeout cleanup")

    def test_pass_and_nonzero_keep_result_shape_and_environment(self):
        code = (
            "import json,os; print(json.dumps({'path':os.environ.get('PATH'),"
            "'unbuffered':os.environ.get('PYTHONUNBUFFERED'),"
            "'extra':os.environ.get('BLIND_SNIPER_TEST_EXTRA')}))"
        )
        with patch.dict(os.environ, {"BLIND_SNIPER_TEST_EXTRA": "must-not-leak"}):
            passed = self.run_python(code)
            failed = self.run_python("import sys; print('bad', file=sys.stderr); sys.exit(7)")

        self.assertEqual(
            set(passed), {"command_id", "status", "exit_code", "stdout_excerpt", "stderr_excerpt"}
        )
        self.assertEqual((passed["status"], passed["exit_code"]), ("PASS", 0))
        observed_env = json.loads(passed["stdout_excerpt"])
        self.assertEqual(observed_env["path"], os.environ.get("PATH", ""))
        self.assertEqual(observed_env["unbuffered"], "1")
        self.assertIsNone(observed_env["extra"])
        self.assertEqual((failed["status"], failed["exit_code"]), ("FAIL", 7))
        self.assertEqual(failed["stderr_excerpt"], "bad\n")

    def test_large_output_is_drained_but_only_tail_is_retained(self):
        expected = "z" * tool_runtime.MAX_TOOL_OUTPUT_CHARS
        result = self.run_python(
            f"import sys; sys.stdout.write('x'*500000 + {expected!r})"
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["stdout_excerpt"]), tool_runtime.MAX_TOOL_OUTPUT_CHARS)
        self.assertEqual(result["stdout_excerpt"], expected)

    def test_timeout_with_escaped_descendant_holding_pipes_is_bounded(self):
        pid_file = self.root / "escaped.pid"
        child = "import time; time.sleep(30)"
        parent = (
            "import subprocess,sys,time; "
            f"p=subprocess.Popen([sys.executable,'-c',{child!r}], start_new_session=True); "
            f"open({str(pid_file)!r},'w').write(str(p.pid)); "
            "time.sleep(30)"
        )
        started = time.monotonic()
        result = self.run_python(parent, timeout=1)
        elapsed = time.monotonic() - started
        self.assertEqual(result["status"], "TIMED_OUT")
        self.assertLess(elapsed, 2.5)
        self.assertTrue(pid_file.exists())
        escaped_pid = int(pid_file.read_text(encoding="utf-8"))
        try:
            os.kill(escaped_pid, 0)
        except ProcessLookupError:
            self.fail("escaped descendant unexpectedly exited before cleanup assertion")
        finally:
            try:
                os.kill(escaped_pid, 9)
            except ProcessLookupError:
                pass

    def test_normal_parent_exit_drains_briefly_then_kills_background_group(self):
        pid_file = self.root / "background.pid"
        child = "import time; time.sleep(30)"
        parent = (
            "import subprocess,sys; "
            f"p=subprocess.Popen([sys.executable,'-c',{child!r}]); "
            f"open({str(pid_file)!r},'w').write(str(p.pid))"
        )
        started = time.monotonic()
        result = self.run_python(parent)
        elapsed = time.monotonic() - started
        self.assertEqual((result["status"], result["exit_code"]), ("PASS", 0))
        self.assertLess(elapsed, 1.5)
        self.assertTrue(pid_file.exists())
        background_pid = int(pid_file.read_text(encoding="utf-8"))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if not process_is_running(background_pid):
                break
            time.sleep(0.02)
        else:
            self.fail(f"background process {background_pid} still exists after normal exit cleanup")

    def test_timeout_uses_term_before_kill_when_child_exits_on_term(self):
        processes = []
        real_popen = tool_runtime.PROCESS_POPEN

        def capture_process(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        started = time.monotonic()
        self.runtime.command_timeout = 0.2
        with patch.dict(tool_runtime.COMMANDS, {
            "unit-tests": [sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, lambda *_: exit(0)); time.sleep(30)"],
        }), patch.object(tool_runtime, "PROCESS_POPEN", side_effect=capture_process):
            result = self.runtime._run_verification({"command_id": "unit-tests"})
        elapsed = time.monotonic() - started
        self.assertEqual(result["status"], "TIMED_OUT")
        self.assertLess(elapsed, 0.2 + tool_runtime.PROCESS_TERMINATION_GRACE_SECONDS / 2)
        self.assertIsNotNone(processes[0].poll())
        with self.assertRaises(ProcessLookupError):
            os.killpg(processes[0].pid, 0)

    def test_timeout_kills_child_that_ignores_term(self):
        self.runtime.command_timeout = 0.2
        processes = []
        real_popen = tool_runtime.PROCESS_POPEN

        def capture_process(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        with patch.object(tool_runtime, "PROCESS_TERMINATION_GRACE_SECONDS", 0.1), patch.dict(
            tool_runtime.COMMANDS,
            {"unit-tests": [sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"]},
        ), patch.object(tool_runtime, "PROCESS_POPEN", side_effect=capture_process):
            result = self.runtime._run_verification({"command_id": "unit-tests"})
        process = processes[0]
        self.assertEqual(result["status"], "TIMED_OUT")
        self.assertIsNotNone(process.poll())
        with self.assertRaises(ProcessLookupError):
            os.killpg(process.pid, 0)

    def test_selector_failure_closes_pipes_and_reaps_child(self):
        processes = []
        real_popen = tool_runtime.PROCESS_POPEN

        def capture_process(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        with patch.dict(tool_runtime.COMMANDS, {
            "unit-tests": [sys.executable, "-c", "import time; time.sleep(30)"],
        }), patch.object(tool_runtime, "PROCESS_POPEN", side_effect=capture_process), patch.object(
            tool_runtime.selectors.DefaultSelector, "register", side_effect=RuntimeError("injected selector failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected selector failure"):
                self.runtime._run_verification({"command_id": "unit-tests"})
        process = processes[0]
        self.assertTrue(process.stdout.closed)
        self.assertTrue(process.stderr.closed)
        self.assertIsNotNone(process.poll())
        with self.assertRaises(ProcessLookupError):
            os.killpg(process.pid, 0)

    def test_timeout_receipt_redacts_secret_sentinel(self):
        sentinel = "sk-test-secret-sentinel-123456789"
        result = self.run_python(
            f"import sys,time; print({sentinel!r}, flush=True); time.sleep(30)", timeout=0.2,
        )
        self.assertEqual(result["status"], "TIMED_OUT")
        self.assertNotIn(sentinel, result["stdout_excerpt"] + result["stderr_excerpt"])


if __name__ == "__main__":
    unittest.main()
