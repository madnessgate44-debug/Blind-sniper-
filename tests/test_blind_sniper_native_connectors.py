from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from dataclasses import replace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.blind_sniper_connectors import (  # noqa: E402
    BUILTIN_SPECS, ConnectorRegistry, ConnectorStatus, ROLES, _utc_now_iso,
)
from scripts.blind_sniper_native_connectors import (  # noqa: E402
    FilesConnector, GitConnector, TerminalConnector, run_process,
)


def registry(connector, operations):
    spec = replace(BUILTIN_SPECS[connector.connector_id],
                   operations=operations)
    reg = ConnectorRegistry(specs={connector.connector_id: spec}, env={}, connectors=[connector])
    reg._statuses[connector.connector_id] = ConnectorStatus(
        connector_id=connector.connector_id, auth_status="verified", health="healthy",
        last_verified_at=_utc_now_iso(), operations_available=operations, checked_by="test")
    return reg


class TestNativeConnectors(unittest.TestCase):
    def test_process_tree_is_killed_and_all_recorded_pids_disappear(self):
        with tempfile.TemporaryDirectory() as tmp:
            pids = Path(tmp) / "pids"
            code = ("import os,subprocess,sys,time; "
                    "g=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                    "open(sys.argv[1],'w').write(str(os.getpid())+' '+str(g.pid)); time.sleep(60)")
            result = run_process([sys.executable, "-c", code, str(pids)], root=tmp, timeout_s=0.5)
            self.assertTrue(result["timed_out"], result)
            self.assertTrue(result["group_dead"], result)
            for pid in map(int, pids.read_text().split()):
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.03)
                else:
                    self.fail(f"process {pid} remained after group kill")

    def test_sigterm_ignoring_and_setsid_descendants_are_killed(self):
        with tempfile.TemporaryDirectory() as tmp:
            pids = Path(tmp) / "pids"
            child = ("import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)")
            code = ("import os,subprocess,sys,time,signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                    f"a=subprocess.Popen([sys.executable,'-c',{child!r}]); "
                    f"b=subprocess.Popen([sys.executable,'-c',{child!r}], start_new_session=True); "
                    "open(sys.argv[1],'w').write(' '.join(map(str,[os.getpid(),a.pid,b.pid]))); time.sleep(60)")
            result = run_process([sys.executable, "-c", code, str(pids)], root=tmp, timeout_s=0.6)
            self.assertTrue(result["timed_out"] and result["group_dead"], result)
            listed = list(map(int, pids.read_text().split()))
            self.assertEqual(len(listed), 3)
            deadline = time.monotonic() + 4
            def alive(pid):
                try:
                    with open(f"/proc/{pid}/stat") as stat_file:
                        return stat_file.read().rsplit(")", 1)[1].split()[0] != "Z"
                except OSError:
                    return False
            while time.monotonic() < deadline and any(alive(p) for p in listed):
                time.sleep(0.03)
            self.assertEqual([p for p in listed if alive(p)], [])

    def test_early_mutation_is_unknown_and_registry_refuses_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "landed"
            py = os.path.realpath(sys.executable)
            connector = TerminalConnector(tmp, {py})
            reg = registry(connector, ["run_command"])
            args = {"argv": [py, "-c", "import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text('yes'); time.sleep(30)", str(marker)]}
            with patch.dict(ROLES, {"test_terminal": [("terminal", "*")]}):
                call = lambda: reg.call("test_terminal", "terminal", "run_command", args,
                                         ["terminal.run_command"], timeout_s=0.4)
                first = call()
                self.assertTrue(marker.exists())
                self.assertEqual(first["failure_kind"], "timeout_partial_unknown", first)
                self.assertEqual(call()["failure_kind"], "execution_state_unknown")

    def test_readonly_timeout_is_retryable_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            connector = TerminalConnector(tmp, {os.path.realpath(sys.executable)})
            # Exercise registry classification with a native process-backed, read-only tool.
            connector.tools = lambda: [{"name": "read", "side_effects": "read_only",
                                        "input_schema": {"type": "object", "properties": {},
                                                         "required": [], "additionalProperties": False}}]
            connector.call = lambda tool_name, arguments, *, timeout_s, cancel=None: run_process(
                [sys.executable, "-c", "import time; time.sleep(20)"], root=tmp,
                timeout_s=timeout_s, cancel=cancel)
            reg = registry(connector, ["read"])
            with patch.dict(ROLES, {"test_terminal": [("terminal", "*")]}):
                got = reg.call("test_terminal", "terminal", "read", {}, ["terminal.read"], timeout_s=0.3)
                self.assertEqual(got["failure_kind"], "timeout", got)

    def test_cancel_event_kills_process_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            event = threading.Event()
            timer = threading.Timer(0.2, event.set)
            timer.start()
            result = run_process([sys.executable, "-c", "import time; time.sleep(20)"],
                                 root=tmp, timeout_s=10, cancel=event)
            timer.join()
            self.assertTrue(result["timed_out"])
            self.assertTrue(result["group_dead"])

    def test_file_paths_reject_traversal_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            (root / "escape").symlink_to(other, target_is_directory=True)
            files = FilesConnector(root)
            for path in ("../outside", str(Path(other) / "file"), "escape/file"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    files.call("read_file", {"path": path}, timeout_s=1)

    def test_files_read_write_list_and_size_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = FilesConnector(tmp, output_cap=128)
            files.call("write_file", {"path": "a.txt", "content": "hello"}, timeout_s=2)
            self.assertEqual(files.call("read_file", {"path": "a.txt"}, timeout_s=2)["data"], "hello")
            self.assertIn("a.txt", files.call("list_dir", {"path": "."}, timeout_s=2)["entries"])
            with self.assertRaises(ValueError):
                files.call("write_file", {"path": "big", "content": "x" * (4 * 1024 * 1024 + 1)}, timeout_s=1)

    def test_terminal_allowlist_and_shell_metacharacters_are_inert(self):
        with tempfile.TemporaryDirectory() as tmp:
            py = os.path.realpath(sys.executable)
            term = TerminalConnector(tmp, {py})
            with self.assertRaises(ValueError):
                term.call("run_command", {"argv": ["/bin/echo", "no"]}, timeout_s=1)
            marker = Path(tmp) / "should-not-exist"
            result = term.call("run_command", {"argv": [py, "-c", "import sys; print(sys.argv[1])",
                                                          f"; touch {marker}"]}, timeout_s=2)
            self.assertIn(f"; touch {marker}", result["output"])
            self.assertFalse(marker.exists())

    def test_child_cannot_see_inherited_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = "BS_NATIVE_TEST_SECRET"
            previous = os.environ.get(key)
            os.environ[key] = "hidden-value-123"
            try:
                result = run_process([sys.executable, "-c", "import os; print(os.getenv('BS_NATIVE_TEST_SECRET','absent'))"],
                                     root=tmp, timeout_s=2)
            finally:
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous
            self.assertEqual(result["output"].strip(), "absent")
            self.assertNotIn("hidden-value-123", json.dumps(result))

    def test_results_redact_the_helper_environment_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_process([sys.executable, "-c", "import os; print(os.environ['PATH']); print(os.environ['HOME']); print(os.environ['LANG'])"],
                                 root=tmp, timeout_s=2)
            for value in (os.defpath, "C.UTF-8"):
                self.assertNotIn(value, result["output"])
            self.assertNotIn("bs-native-home-", result["output"])

    def test_output_cap_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_process([sys.executable, "-c", "print('x'*10000)"], root=tmp,
                                 timeout_s=2, output_cap=100)
            self.assertEqual(len(result["output"].encode()), 100)
            self.assertTrue(result["output_truncated"])

    @unittest.skipUnless(shutil.which("git"), "git executable unavailable")
    def test_git_readonly_tools_on_temporary_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run([shutil.which("git"), "init", "-q", str(root)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run([shutil.which("git"), "-C", tmp, "-c", "user.name=Test", "-c",
                            "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "start"],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            git = GitConnector(root)
            status = git.call("status", {}, timeout_s=3)
            log = git.call("log", {"limit": 1}, timeout_s=3)
            diff = git.call("diff", {}, timeout_s=3)
            self.assertIn("##", status["output"])
            self.assertIn("start", log["output"])
            self.assertEqual(diff["output"], "")
            self.assertTrue(all(x["side_effects"] == "read_only" for x in git.tools()))


if __name__ == "__main__":
    unittest.main()
