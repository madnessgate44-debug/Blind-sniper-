from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_mcp_server import BrowserDispatchError, BrowserMCP, TOOLS, handle  # noqa: E402


class FakeServer:
    def __init__(self):
        self.calls = []

    def start(self, url):
        self.calls.append(("start", url))
        return {"opened": url}

    def resume(self, task_id, run_id, session_id):
        self.calls.append(("resume", task_id, run_id, session_id))
        return {"resumed": task_id}

    def action(self, action, args):
        if action == "close":
            raise ValueError("use browser.close for session shutdown")
        if action == "detach":
            raise ValueError("use browser.detach for session detachment")
        self.calls.append(("action", action, args))
        return {"action": action, "args": args}

    def status(self):
        self.calls.append(("status",))
        return {"url": "https://example.org/"}

    def close(self):
        self.calls.append(("close",))
        return {"lease_released": True}


class BrowserMCPStatusTests(unittest.TestCase):
    def _server(self, *, url_exit=0):
        server = BrowserMCP.__new__(BrowserMCP)
        server.active = {}

        def dispatch(action, args):
            if action == "get-url":
                return {
                    "output": json.dumps({"success": True, "data": {"url": "https://example.org/"}}),
                    "receipt": {"action": action, "exit_code": url_exit},
                }
            if action == "get-title":
                return {
                    "output": json.dumps({"success": True, "data": {"title": "Example Domain"}}),
                    "receipt": {"action": action, "exit_code": 0},
                }
            if action == "snapshot":
                return {
                    "output": json.dumps({"success": True, "data": {"snapshot": "- heading Example"}}),
                    "receipt": {"action": action, "exit_code": 0},
                }
            return {
                "output": "{}",
                "receipt": {"action": action, "exit_code": 0, "artifact_paths": ["/private/browser.png"]},
            }

        server._dispatch = dispatch
        return server

    def test_status_returns_normalized_url_visible_text_and_screenshot(self):
        result = self._server().status()
        self.assertEqual(result["url"], "https://example.org/")
        self.assertEqual(result["title"], "Example Domain")
        self.assertIn("browser.close", result["available_actions"])
        self.assertIn("browser.detach", result["available_actions"])
        self.assertIn("fill", result["approval_required_actions"])
        self.assertEqual(result["visible_text"], "- heading Example")
        self.assertEqual(result["screenshot_reference"], ["/private/browser.png"])
        self.assertTrue(all(row["exit_code"] == 0 for row in result["receipts"]))
        self.assertFalse(result["user_action_required"])
        self.assertIsNone(result["handoff_type"])

    def test_status_detects_captcha_and_pauses_browser_actions(self):
        server = self._server()
        def dispatch(action, args):
            output = {
                "get-url": json.dumps({"data": {"url": "https://example.org/"}}),
                "get-title": json.dumps({"data": {"title": "Challenge"}}),
                "snapshot": json.dumps({"data": {"snapshot": "Please complete the following challenge to confirm this search was made by a human. Select all squares containing a duck."}}),
                "screenshot": "{}",
            }[action]
            receipt = {"action": action, "exit_code": 0}
            if action == "screenshot":
                receipt["artifact_paths"] = ["/private/challenge.png"]
            return {"output": output, "receipt": receipt}
        server._dispatch = dispatch
        result = server.status()
        self.assertTrue(result["user_action_required"])
        self.assertEqual(result["handoff_type"], "captcha")
        with self.assertRaisesRegex(PermissionError, "CAPTCHA/MFA bypass is not supported"):
            server.action("click", ["#continue"])

    def test_status_detects_mfa_and_hands_off(self):
        server = self._server()
        def dispatch(action, args):
            output = {
                "get-url": json.dumps({"data": {"url": "https://example.org/"}}),
                "get-title": json.dumps({"data": {"title": "MFA"}}),
                "snapshot": json.dumps({"data": {"snapshot": "Enter the one-time code from your authenticator app"}}),
                "screenshot": "{}",
            }[action]
            receipt = {"action": action, "exit_code": 0}
            if action == "screenshot":
                receipt["artifact_paths"] = ["/private/mfa.png"]
            return {"output": output, "receipt": receipt}
        server._dispatch = dispatch
        result = server.status()
        self.assertTrue(result["user_action_required"])
        self.assertEqual(result["handoff_type"], "mfa")

    def test_status_fails_closed_when_url_read_fails(self):
        with self.assertRaisesRegex(BrowserDispatchError, "status action failed: get-url"):
            self._server(url_exit=1).status()


class BrowserMCPProtocolTests(unittest.TestCase):
    def test_initialize_negotiates_tools_capability(self):
        response = handle(FakeServer(), {
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}
        })
        self.assertEqual(response["result"]["capabilities"], {"tools": {}})
        self.assertEqual(response["result"]["protocolVersion"], "2025-03-26")

    def test_tools_list_exposes_only_native_browser_tools(self):
        response = handle(FakeServer(), {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list"
        })
        self.assertEqual(
            {row["name"] for row in response["result"]["tools"]},
            {row["name"] for row in TOOLS},
        )
        self.assertEqual(len(TOOLS), 6)
        self.assertIn("browser.detach", {row["name"] for row in TOOLS})

    def test_failed_browser_start_cancels_task_and_releases_lease(self):
        class Ledger:
            def __init__(self):
                self.transitions = []
                self.released = False
            def append(self, **kwargs):
                return {}
            def claim_task(self, **kwargs):
                return {"claimed": True}
            def append_transition_if_lease(self, **kwargs):
                self.transitions.append(kwargs["payload"]["state"])
                return {}
            def release_task(self, **kwargs):
                self.released = True
                return {"released": True}
        server = BrowserMCP.__new__(BrowserMCP)
        server.ledger = Ledger()
        server.browser_state = Path("/tmp/blind-sniper-browser-test")
        server.active = None
        server._dispatch = lambda action, args: (_ for _ in ()).throw(RuntimeError("blocked destination"))
        with self.assertRaisesRegex(RuntimeError, "blocked destination"):
            server.start("https://127.0.0.1/")
        self.assertIsNone(server.active)
        self.assertTrue(server.ledger.released)
        self.assertEqual(server.ledger.transitions[-1]["status"], "CANCELLED")

        failed_result_server = BrowserMCP.__new__(BrowserMCP)
        failed_result_server.ledger = Ledger()
        failed_result_server.browser_state = Path("/tmp/blind-sniper-browser-test")
        failed_result_server.active = None
        failed_result_server._dispatch = lambda action, args: {"receipt": {"exit_code": 2}}
        with self.assertRaisesRegex(BrowserDispatchError, "did not establish"):
            failed_result_server.start("https://127.0.0.1/")
        self.assertIsNone(failed_result_server.active)
        self.assertTrue(failed_result_server.ledger.released)
        self.assertEqual(failed_result_server.ledger.transitions[-1]["status"], "CANCELLED")

    def test_start_routes_to_server_and_returns_structured_content(self):
        server = FakeServer()
        response = handle(server, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "browser.start", "arguments": {"url": "https://example.org"}},
        })
        self.assertEqual(server.calls, [("start", "https://example.org")])
        self.assertEqual(response["result"]["structuredContent"], {"opened": "https://example.org"})

    def test_action_rejects_non_string_argument_array(self):
        response = handle(FakeServer(), {
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "browser.action", "arguments": {"action": "fill", "args": ["#q", 4]}},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("array of strings", response["result"]["content"][0]["text"])

    def test_unknown_tool_is_invalid_params(self):
        response = handle(FakeServer(), {
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "browser.no_such_tool", "arguments": {}},
        })
        self.assertEqual(response["error"]["code"], -32602)

    def test_initialized_notification_has_no_response(self):
        response = handle(FakeServer(), {
            "jsonrpc": "2.0", "method": "notifications/initialized"
        })
        self.assertIsNone(response)

    def test_nested_browser_receipt_failure_is_reported_as_tool_error(self):
        from blind_sniper_mcp_server import _result
        response = _result({"browser": {"receipt": {"exit_code": 2}}})
        self.assertTrue(response["isError"])

    def test_non_object_arguments_return_json_rpc_error(self):
        response = handle(FakeServer(), {
            "jsonrpc": "2.0", "id": 6, "method": "tools/call",
            "params": {"name": "browser.status", "arguments": []},
        })
        self.assertEqual(response["error"]["code"], -32602)

    def test_detach_closes_browser_but_retains_task_lease(self):
        server = BrowserMCP.__new__(BrowserMCP)
        server.active = {"task_id": "task-1", "run_id": "run-1", "session_id": "session-1"}
        dispatched = []
        server._dispatch = lambda action, args: (dispatched.append(action) or {"receipt": {"exit_code": 0, "action": action}})
        result = server.detach()
        self.assertEqual(dispatched, ["detach"])
        self.assertTrue(result["lease_retained"])
        self.assertEqual(result["session"]["session_id"], "session-1")
        self.assertIsNone(server.active)

    def test_failed_detach_keeps_active_session_and_lease(self):
        server = BrowserMCP.__new__(BrowserMCP)
        server.active = {"task_id": "task-1", "run_id": "run-1", "session_id": "session-1"}
        server._dispatch = lambda action, args: {"receipt": {"exit_code": 1, "action": action}}
        with self.assertRaisesRegex(BrowserDispatchError, "lease remains active"):
            server.detach()
        self.assertIsNotNone(server.active)

    def test_resume_reclaims_expired_lease_for_same_native_owner(self):
        class ExpiredLeaseLedger:
            def __init__(self):
                self.claims = []
            def events(self, task_id):
                return [{"payload": {"state": {"status": "EXECUTING", "implementer_id": "blind-sniper"}}}]
            def claim_task(self, **kwargs):
                self.claims.append(kwargs)
                return {"claimed": True}
        server = BrowserMCP.__new__(BrowserMCP)
        server.active = None
        server.ledger = ExpiredLeaseLedger()
        server._dispatch = lambda action, args: {"receipt": {"exit_code": 0, "action": action}}
        result = server.resume("task-1", "run-1", "session-1")
        self.assertEqual(result["session"]["task_id"], "task-1")
        self.assertEqual(server.ledger.claims[0]["owner_id"], "blind-sniper-mcp-host")
        self.assertTrue(server.ledger.claims[0]["idempotency_key"].startswith("task-1:mcp-lease:resume:"))

    def test_generic_action_cannot_bypass_session_close_lifecycle(self):
        response = handle(FakeServer(), {
            "jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {"name": "browser.action", "arguments": {"action": "close"}},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("browser.close", response["result"]["content"][0]["text"])
        response = handle(FakeServer(), {
            "jsonrpc": "2.0", "id": 8, "method": "tools/call",
            "params": {"name": "browser.action", "arguments": {"action": "detach"}},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("browser.detach", response["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
