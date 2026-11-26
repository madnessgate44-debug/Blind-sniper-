from __future__ import annotations

import hashlib
import http.server
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from blind_sniper_daemon import BlindSniperDaemon, PrivateTaskStore
from blind_sniper_ledger import TaskLedger
from blind_sniper_model_worker import ModelWorker, NativeModelInvoker
from blind_sniper_tool_runtime import NativeToolRuntime
from blind_sniper_worker import DurableQueue


def _make_tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments),
        },
    }


def _assistant_tool_reply(tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls,
                },
                "finish_reason": "tool_calls",
            }
        ]
    }


def _assistant_text_reply(text: str) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "finish_reason": "stop",
            }
        ]
    }


class ScriptedProvider:
    # This proves integration plumbing only and is not evidence of model quality.
    def __init__(self, scripted_replies: list[dict[str, Any]]) -> None:
        self.replies = list(scripted_replies)
        self.recorded_requests: list[dict[str, Any]] = []
        self._index = 0
        self._lock = threading.Lock()

    def next_reply(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.recorded_requests.append(payload)
            if self._index < len(self.replies):
                reply = self.replies[self._index]
                self._index += 1
                return reply
            return _assistant_text_reply("No more scripted replies.")

    @property
    def request_count(self) -> int:
        with self._lock:
            return len(self.recorded_requests)


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _start_provider_server(
    provider: ScriptedProvider,
) -> tuple[_ThreadingHTTPServer, str, threading.Thread]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path != "/chat/completions":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            parsed_body = json.loads(raw_body.decode("utf-8"))
            response_obj = provider.next_reply(parsed_body)
            encoded = json.dumps(response_obj).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = _ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, base_url, thread


def build_stack(
    state_dir: Path,
    workspace_root: Path,
    base_url: str,
) -> tuple[
    PrivateTaskStore,
    TaskLedger,
    DurableQueue,
    NativeToolRuntime,
    NativeModelInvoker,
    ModelWorker,
    BlindSniperDaemon,
]:
    allowed_agents = frozenset({"builder"})
    store = PrivateTaskStore(state_dir=state_dir, workspace_root=workspace_root)
    ledger = TaskLedger(store.ledger_path)
    queue = DurableQueue(ledger)
    tool_runtime = NativeToolRuntime(
        queue=queue,
        workspace_root=workspace_root,
        command_timeout=60,
        handoff_state_dir=store.handoff_dir,
        allowed_agent_ids=allowed_agents,
    )
    invoker = NativeModelInvoker(
        base_url=base_url,
        model="scripted-model-v1",
        tool_runtime=tool_runtime,
    )
    worker = ModelWorker(
        invoker=invoker,
        max_concurrency=1,
        timeout_seconds=60,
        max_retries=0,
    )
    host_policy = {
        "permission_profile": "workspace_write",
        "tool_allowlist": ("repo.read_file", "repo.write_file", "verification.run"),
        "allowed_paths": ("fixture_app/calc.py",),
        "browser_approval_reference": "",
    }
    daemon = BlindSniperDaemon(
        queue=queue,
        worker=worker,
        owner_id="test-owner",
        store=store,
        lease_seconds=900,
        max_tasks_per_cycle=10,
        host_policy=host_policy,
        allowed_agent_ids=allowed_agents,
    )
    return store, ledger, queue, tool_runtime, invoker, worker, daemon


def _write_task_file(task_dir: Path, task_id: str, objective: str) -> Path:
    task_path = task_dir / f"{task_id}.json"
    task_doc = {
        "task_id": task_id,
        "agent_id": "builder",
        "objective": objective,
        "payload": {"target": "fixture_app/calc.py"},
    }
    task_path.write_text(json.dumps(task_doc), encoding="utf-8")
    os.chmod(task_path, 0o600)
    return task_path


def _run_fixture_unittest(workspace_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
        check=False,
    )


class BlindSniperFixtureSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.root_tmp = Path(self._tmp_ctx.name)
        self.workspace_root = self.root_tmp / "workspace"
        self.state_dir = self.root_tmp / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.state_dir, 0o700)

        (self.workspace_root / "fixture_app").mkdir(parents=True, exist_ok=True)
        (self.workspace_root / "tests").mkdir(parents=True, exist_ok=True)
        (self.workspace_root / "chatgpt-home" / "runtime").mkdir(parents=True, exist_ok=True)

        (self.workspace_root / "fixture_app" / "__init__.py").write_text("", encoding="utf-8")
        self.calc_path = self.workspace_root / "fixture_app" / "calc.py"
        self.calc_path.write_text(
            "def add(a, b):\n    return a - b\n",
            encoding="utf-8",
        )
        self.test_calc_path = self.workspace_root / "tests" / "test_calc.py"
        self.test_calc_path.write_text(
            "import unittest\n"
            "from fixture_app.calc import add\n\n\n"
            "class CalcTests(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n"
            "        self.assertEqual(add(-1, 1), 0)\n",
            encoding="utf-8",
        )
        (self.workspace_root / "chatgpt-home" / "runtime" / "agents.json").write_text(
            json.dumps({"agents": [{"id": "builder"}]}),
            encoding="utf-8",
        )

        self._servers: list[tuple[_ThreadingHTTPServer, threading.Thread]] = []

    def tearDown(self) -> None:
        for server, thread in self._servers:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self._tmp_ctx.cleanup()

    def _register_server(self, provider: ScriptedProvider) -> str:
        server, base_url, thread = _start_provider_server(provider)
        self._servers.append((server, thread))
        return base_url

    def test_happy_path_and_restart_persistence(self) -> None:
        fixed_calc = "def add(a, b):\n    return a + b\n"
        provider = ScriptedProvider(
            [
                _assistant_tool_reply(
                    [_make_tool_call("call-1", "repo.read_file", {"path": "fixture_app/calc.py"})]
                ),
                _assistant_tool_reply(
                    [
                        _make_tool_call(
                            "call-2",
                            "repo.write_file",
                            {"path": "fixture_app/calc.py", "content": fixed_calc},
                        )
                    ]
                ),
                _assistant_tool_reply(
                    [_make_tool_call("call-3", "verification.run", {"command_id": "unit-tests"})]
                ),
                _assistant_text_reply("Fixed add and verified unit tests."),
            ]
        )
        base_url = self._register_server(provider)

        store, ledger, queue, runtime, invoker, worker, daemon = build_stack(
            self.state_dir, self.workspace_root, base_url
        )
        task_id = "job-fix-add-001"
        _write_task_file(store.task_dir, task_id, "Fix add(a, b) in fixture_app/calc.py")

        result = daemon.run_once()
        counts = result["counts"]
        self.assertEqual(counts["completed"], 1)
        self.assertEqual(counts["errors"], 0)
        self.assertEqual(self.calc_path.read_text(encoding="utf-8"), fixed_calc)

        proc = _run_fixture_unittest(self.workspace_root)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

        self.assertEqual(provider.request_count, 4)
        for req in provider.recorded_requests[1:]:
            serialized = json.dumps(req)
            self.assertIn("tool", serialized)

        receipts = list(store.receipt_dir.glob("*.json"))
        self.assertEqual(len(receipts), 1)
        receipt_path = receipts[0]
        receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt_data.get("status"), "PASS")
        tool_receipts = receipt_data.get("tool_receipts", [])
        self.assertEqual(len(tool_receipts), 3)

        status_info = queue.status(task_id)
        self.assertIsNotNone(status_info)
        self.assertEqual(status_info["status"], "COMPLETED")

        receipt_hash_before = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        ledger_size_before = store.ledger_path.stat().st_size

        del daemon, worker, invoker, runtime, queue, ledger, store

        store2, ledger2, queue2, runtime2, invoker2, worker2, daemon2 = build_stack(
            self.state_dir, self.workspace_root, base_url
        )
        status_after = queue2.status(task_id)
        self.assertIsNotNone(status_after)
        self.assertEqual(status_after["status"], "COMPLETED")
        self.assertTrue(receipt_path.exists())
        self.assertEqual(
            hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
            receipt_hash_before,
        )
        self.assertGreaterEqual(store2.ledger_path.stat().st_size, ledger_size_before)

        second_result = daemon2.run_once()
        self.assertEqual(second_result["counts"]["skipped"], 1)
        self.assertEqual(second_result["counts"]["completed"], 0)
        self.assertEqual(provider.request_count, 4)
        del daemon2, worker2, invoker2, runtime2, queue2, ledger2, store2

    def test_negative_disallowed_path_and_path_escape(self) -> None:
        original_test_calc = self.test_calc_path.read_text(encoding="utf-8")
        escaped_target = self.root_tmp / "x"

        provider_a = ScriptedProvider(
            [
                _assistant_tool_reply(
                    [
                        _make_tool_call(
                            "call-bad-path",
                            "repo.write_file",
                            {"path": "tests/test_calc.py", "content": "# tampered\n"},
                        )
                    ]
                ),
                _assistant_text_reply("Attempted test edit."),
            ]
        )
        base_url_a = self._register_server(provider_a)
        store_a, _, queue_a, _, _, _, daemon_a = build_stack(
            self.state_dir, self.workspace_root, base_url_a
        )
        task_a = "job-neg-disallowed-path-001"
        _write_task_file(store_a.task_dir, task_a, "Try writing tests/test_calc.py")
        result_a = daemon_a.run_once()

        self.assertEqual(result_a["counts"]["completed"], 0)
        self.assertEqual(self.test_calc_path.read_text(encoding="utf-8"), original_test_calc)
        status_a = queue_a.status(task_a)
        self.assertIsNotNone(status_a)
        self.assertNotEqual(status_a.get("status"), "COMPLETED")
        receipts_a = list(store_a.receipt_dir.glob(f"{task_a}*.json"))
        self.assertEqual(len(receipts_a), 1)
        self.assertTrue(receipts_a[0].exists())
        receipt_data_a = json.loads(receipts_a[0].read_text(encoding="utf-8"))
        self.assertEqual(receipt_data_a.get("status"), "FAIL")
        self.assertIn("tool_receipts_not_passing", receipt_data_a.get("error", ""))
        tool_receipts_a = receipt_data_a.get("tool_receipts", [])
        self.assertEqual(len(tool_receipts_a), 1)
        self.assertEqual(tool_receipts_a[0].get("tool_name"), "repo.write_file")
        self.assertEqual(tool_receipts_a[0].get("status"), "FAIL")

        provider_b = ScriptedProvider(
            [
                _assistant_tool_reply(
                    [
                        _make_tool_call(
                            "call-escape",
                            "repo.write_file",
                            {"path": "../x", "content": "escaped\n"},
                        )
                    ]
                ),
                _assistant_text_reply("Attempted escape write."),
            ]
        )
        base_url_b = self._register_server(provider_b)
        state_dir_b = self.root_tmp / "state_b"
        state_dir_b.mkdir(parents=True, exist_ok=True)
        os.chmod(state_dir_b, 0o700)
        store_b, _, queue_b, _, _, _, daemon_b = build_stack(
            state_dir_b, self.workspace_root, base_url_b
        )
        task_b = "job-neg-escape-001"
        _write_task_file(store_b.task_dir, task_b, "Try path escape ../x")
        result_b = daemon_b.run_once()

        self.assertEqual(result_b["counts"]["completed"], 0)
        self.assertFalse(escaped_target.exists())
        status_b = queue_b.status(task_b)
        self.assertIsNotNone(status_b)
        self.assertNotEqual(status_b.get("status"), "COMPLETED")
        receipts_b = list(store_b.receipt_dir.glob(f"{task_b}*.json"))
        self.assertEqual(len(receipts_b), 1)
        self.assertTrue(receipts_b[0].exists())
        receipt_data_b = json.loads(receipts_b[0].read_text(encoding="utf-8"))
        self.assertEqual(receipt_data_b.get("status"), "FAIL")
        self.assertIn("tool_receipts_not_passing", receipt_data_b.get("error", ""))
        tool_receipts_b = receipt_data_b.get("tool_receipts", [])
        self.assertEqual(len(tool_receipts_b), 1)
        self.assertEqual(tool_receipts_b[0].get("tool_name"), "repo.write_file")
        self.assertEqual(tool_receipts_b[0].get("status"), "FAIL")

    def test_strict_redactor_still_refuses_task_prefixed_long_id(self) -> None:
        # Control: main's strict redactor is unchanged, so a long "task-" id is
        # still refused and the task must not be recorded as COMPLETED.
        provider = ScriptedProvider(
            [_assistant_text_reply("Completed task without tool calls.")]
        )
        base_url = self._register_server(provider)
        store, _, queue, _, _, _, daemon = build_stack(
            self.state_dir, self.workspace_root, base_url
        )
        task_id = "task-disallowed-path-001"
        _write_task_file(store.task_dir, task_id, "Complete task with task- prefix id")

        result = daemon.run_once()
        self.assertEqual(result["counts"]["completed"], 0)
        status_info = queue.status(task_id)
        if status_info is not None:
            self.assertNotEqual(status_info.get("status"), "COMPLETED")

    def test_failing_fixture_acceptance_gate(self) -> None:
        wrong_calc = "def add(a, b):\n    return a * b\n"
        provider = ScriptedProvider(
            [
                _assistant_tool_reply(
                    [_make_tool_call("call-1", "repo.read_file", {"path": "fixture_app/calc.py"})]
                ),
                _assistant_tool_reply(
                    [
                        _make_tool_call(
                            "call-2",
                            "repo.write_file",
                            {"path": "fixture_app/calc.py", "content": wrong_calc},
                        )
                    ]
                ),
                _assistant_tool_reply(
                    [_make_tool_call("call-3", "verification.run", {"command_id": "unit-tests"})]
                ),
                _assistant_text_reply("Fixed add and verified unit tests."),
            ]
        )
        base_url = self._register_server(provider)

        store, ledger, queue, runtime, invoker, worker, daemon = build_stack(
            self.state_dir, self.workspace_root, base_url
        )
        task_id = "job-fail-acceptance-001"
        _write_task_file(store.task_dir, task_id, "Attempt fix in fixture_app/calc.py")

        result = daemon.run_once()
        self.assertEqual(result["counts"]["completed"], 0)

        proc = _run_fixture_unittest(self.workspace_root)
        self.assertNotEqual(proc.returncode, 0)

        receipts = list(store.receipt_dir.glob(f"{task_id}*.json"))
        self.assertEqual(len(receipts), 1)
        receipt_path = receipts[0]
        self.assertTrue(receipt_path.exists())
        receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt_data.get("status"), "FAIL")

        tool_receipts = receipt_data.get("tool_receipts", [])
        ver_receipts = [r for r in tool_receipts if r.get("tool_name") == "verification.run"]
        self.assertEqual(len(ver_receipts), 1)
        self.assertEqual(ver_receipts[0].get("status"), "FAIL")

        status_info = queue.status(task_id)
        self.assertIsNotNone(status_info)
        self.assertNotEqual(status_info.get("status"), "COMPLETED")

        del daemon, worker, invoker, runtime, queue, ledger, store

        _, _, queue2, _, _, _, daemon2 = build_stack(
            self.state_dir, self.workspace_root, base_url
        )
        status_after = queue2.status(task_id)
        self.assertIsNotNone(status_after)
        self.assertNotEqual(status_after.get("status"), "COMPLETED")
        del daemon2, queue2


@unittest.skipUnless(
    bool(os.environ.get("BLIND_SNIPER_SLICE_LIVE_BASE_URL"))
    and bool(os.environ.get("BLIND_SNIPER_SLICE_LIVE_MODEL")),
    "Set BLIND_SNIPER_SLICE_LIVE_BASE_URL and BLIND_SNIPER_SLICE_LIVE_MODEL to run.",
)
class BlindSniperLiveEndpointSliceTests(unittest.TestCase):
    def test_live_endpoint_smoke(self) -> None:
        live_url = os.environ["BLIND_SNIPER_SLICE_LIVE_BASE_URL"]
        live_model = os.environ["BLIND_SNIPER_SLICE_LIVE_MODEL"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws = root / "workspace"
            st = root / "state"
            st.mkdir(parents=True, exist_ok=True)
            os.chmod(st, 0o700)
            (ws / "fixture_app").mkdir(parents=True, exist_ok=True)
            (ws / "tests").mkdir(parents=True, exist_ok=True)
            (ws / "chatgpt-home" / "runtime").mkdir(parents=True, exist_ok=True)
            (ws / "fixture_app" / "__init__.py").write_text("", encoding="utf-8")
            (ws / "fixture_app" / "calc.py").write_text(
                "def add(a, b):\n    return a - b\n", encoding="utf-8"
            )
            (ws / "tests" / "test_calc.py").write_text(
                "import unittest\nfrom fixture_app.calc import add\n\n"
                "class CalcTests(unittest.TestCase):\n"
                "    def test_add(self):\n"
                "        self.assertEqual(add(2, 3), 5)\n"
                "        self.assertEqual(add(-1, 1), 0)\n",
                encoding="utf-8",
            )
            (ws / "chatgpt-home" / "runtime" / "agents.json").write_text(
                json.dumps({"agents": [{"id": "builder"}]}), encoding="utf-8"
            )

            store, _, queue, runtime, _, worker, daemon = build_stack(st, ws, live_url)
            worker.invoker = NativeModelInvoker(
                base_url=live_url, model=live_model, tool_runtime=runtime
            )
            task_id = "live-task-001"
            _write_task_file(store.task_dir, task_id, "Fix add(a, b) in fixture_app/calc.py")
            daemon.run_once()

            proc = _run_fixture_unittest(ws)
            receipts = list(store.receipt_dir.glob("*.json"))
            receipt_count = 0
            task_receipt_status = None
            if receipts:
                data = json.loads(receipts[0].read_text(encoding="utf-8"))
                receipt_count = len(data.get("tool_receipts", []))
                task_receipt_status = data.get("status")

            q_status = queue.status(task_id)
            queue_status = q_status.get("status") if q_status else None
            summary = {
                "status": queue_status,
                "queue_status": queue_status,
                "task_receipt_status": task_receipt_status,
                "tests_passed": proc.returncode == 0,
                "tool_receipts_count": receipt_count,
            }
            print(json.dumps(summary))
            out = os.environ.get("BLIND_SNIPER_SLICE_LIVE_SUMMARY_PATH")
            if out:
                Path(out).write_text(json.dumps(summary), encoding="utf-8")
            if os.environ.get("BLIND_SNIPER_SLICE_LIVE_REQUIRE_PASS") == "1":
                self.assertTrue(summary["tests_passed"], summary)
                self.assertEqual(summary["task_receipt_status"], "PASS", summary)
