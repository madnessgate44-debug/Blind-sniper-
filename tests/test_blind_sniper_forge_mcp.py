"""Contract tests for the Forge Streamable HTTP MCP client adapter.

These prove the transport protocol shape (JSON-RPC 2.0 initialize/tools/list/
tools/call), the disabled-by-default gate, durable-endpoint enforcement, tool
allowlisting, browser-write approval gating, auth failure mapping and redaction.
They do NOT prove a live MCP round trip; the adapter stays BLOCKED until a
durable endpoint and auth are genuinely configured.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from blind_sniper_forge_mcp import ForgeMCPClient, ForgeMCPError


class FakeTransport:
    def __init__(self):
        self.requests = []
        self.responses = []

    def push(self, status, payload):
        self.responses.append((status, json.dumps(payload).encode() if payload is not None else b""))

    def __call__(self, method, url, headers, body, timeout):
        self.requests.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        if self.responses:
            status, raw = self.responses.pop(0)
        else:
            status, raw = 200, b"{}"
        return status, raw, {"content-type": "application/json"}


class ForgeMCPClientTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()

    def client(self, **kwargs):
        kwargs.setdefault("endpoint", "https://forge.example.com/mcp")
        kwargs.setdefault("token", "forge-token-value")
        kwargs.setdefault("transport", self.transport)
        return ForgeMCPClient(**kwargs)

    def test_disabled_without_endpoint(self):
        with self.assertRaisesRegex(ForgeMCPError, "disabled"):
            ForgeMCPClient(endpoint="", token="t", transport=self.transport)

    def test_disabled_without_token(self):
        with self.assertRaisesRegex(ForgeMCPError, "disabled"):
            ForgeMCPClient(endpoint="https://forge.example.com/mcp", token="", transport=self.transport)

    def test_requires_https_endpoint(self):
        with self.assertRaisesRegex(ForgeMCPError, "https"):
            ForgeMCPClient(endpoint="http://forge.example.com/mcp", token="t", transport=self.transport)

    def test_refuses_ephemeral_sandbox_host(self):
        with self.assertRaisesRegex(ForgeMCPError, "ephemeral"):
            ForgeMCPClient(
                endpoint="https://abc123.prod-runtime.all-hands.dev/mcp",
                token="t", transport=self.transport,
            )

    def test_initialize_sends_jsonrpc_and_bearer(self):
        self.transport.push(200, {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05"}})
        self.client().initialize()
        request = self.transport.requests[-1]
        self.assertEqual(request["headers"]["Authorization"], "Bearer forge-token-value")
        body = json.loads(request["body"].decode())
        self.assertEqual(body["method"], "initialize")
        self.assertEqual(body["jsonrpc"], "2.0")

    def test_list_tools_returns_names(self):
        self.transport.push(200, {"jsonrpc": "2.0", "id": 1, "result": {
            "tools": [{"name": "browser_open"}, {"name": "browser_click"}],
        }})
        result = self.client().list_tools()
        self.assertEqual(result["tools"], ["browser_open", "browser_click"])

    def test_call_tool_enforces_allowlist(self):
        client = self.client(tool_allowlist=["browser_open"])
        with self.assertRaisesRegex(ForgeMCPError, "allowlist"):
            client.call_tool("browser_click")

    def test_browser_write_requires_approval_reference(self):
        client = self.client(tool_allowlist=["browser_click"])
        with self.assertRaisesRegex(ForgeMCPError, "approval"):
            client.call_tool("browser_click", {"selector": "#go"})
        self.transport.push(200, {"jsonrpc": "2.0", "id": 1, "result": {"content": []}})
        result = client.call_tool("browser_click", {"selector": "#go"}, approval_reference="owner-approval-1")
        self.assertEqual(result["approval_reference"], "owner-approval-1")

    def test_read_only_tool_does_not_require_approval(self):
        client = self.client(tool_allowlist=["browser_open"])
        self.transport.push(200, {"jsonrpc": "2.0", "id": 1, "result": {"content": []}})
        result = client.call_tool("browser_open", {"url": "https://example.com"})
        self.assertIsNone(result["approval_reference"])

    def test_auth_failure_maps_to_401_error(self):
        self.transport.push(401, {"message": "unauthorized"})
        with self.assertRaisesRegex(ForgeMCPError, "401"):
            self.client().initialize()

    def test_jsonrpc_error_is_surfaced(self):
        self.transport.push(200, {"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "no"}})
        with self.assertRaisesRegex(ForgeMCPError, "error"):
            self.client().initialize()

    def test_receipt_redacts_secrets(self):
        receipt = self.client().receipt(operation="tools/call", result={"note": "ghp_" + "a" * 30})
        self.assertNotIn("ghp_", json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
