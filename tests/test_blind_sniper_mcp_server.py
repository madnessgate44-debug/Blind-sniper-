from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_mcp_server import TOOLS, handle  # noqa: E402


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
        self.calls.append(("action", action, args))
        return {"action": action, "args": args}

    def status(self):
        self.calls.append(("status",))
        return {"url": "https://example.org/"}

    def close(self):
        self.calls.append(("close",))
        return {"lease_released": True}


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
        self.assertEqual(len(TOOLS), 5)

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


if __name__ == "__main__":
    unittest.main()
