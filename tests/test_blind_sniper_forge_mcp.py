"""Contract tests for the Forge MCP Streamable HTTP adapter (mock transport)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_forge_mcp as forge  # noqa: E402


class FakeMCPTransport:
    def __init__(self, *, sse=False, fail_method=None):
        self.requests = []
        self.sse = sse
        self.fail_method = fail_method

    def __call__(self, url, headers, body):
        message = json.loads(body.decode())
        self.requests.append({"url": url, "message": message, "auth": headers.get("Authorization"),
                              "accept": headers.get("Accept")})
        method = message["method"]
        if method == self.fail_method:
            result = {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "nope"}}
        elif method == "initialize":
            result = {"jsonrpc": "2.0", "id": message["id"], "result": {
                "protocolVersion": "2025-06-18", "serverInfo": {"name": "forge"}, "capabilities": {"tools": {}}}}
        elif method == "tools/list":
            result = {"jsonrpc": "2.0", "id": message["id"], "result": {"tools": [
                {"name": "browser_open"}, {"name": "browser_click"}, {"name": "browser_snapshot"}]}}
        elif method == "tools/call":
            result = {"jsonrpc": "2.0", "id": message["id"], "result": {
                "content": [{"type": "text", "text": "ok"}]}}
        else:
            result = {"jsonrpc": "2.0", "id": message["id"], "result": {}}
        if self.sse:
            payload = ("event: message\n" + "data: " + json.dumps(result) + "\n\n").encode()
            return 200, payload, "text/event-stream"
        return 200, json.dumps(result).encode(), "application/json"


class ForgeMCPTests(unittest.TestCase):
    def test_disabled_without_endpoint_or_token(self):
        client = forge.ForgeMCPClient(endpoint="", token="", transport=FakeMCPTransport())
        self.assertFalse(client.enabled)
        with self.assertRaises(forge.ForgeMCPError):
            client.initialize()

    def test_initialize_negotiates_protocol(self):
        transport = FakeMCPTransport()
        client = forge.ForgeMCPClient(endpoint="https://forge.example/mcp", token="t", transport=transport)
        result = client.initialize()
        self.assertEqual(result["protocol_version"], "2025-06-18")
        self.assertEqual(result["server_info"]["name"], "forge")
        self.assertEqual(transport.requests[0]["auth"], "Bearer t")
        self.assertIn("text/event-stream", transport.requests[0]["accept"])

    def test_list_tools_returns_names(self):
        client = forge.ForgeMCPClient(endpoint="https://forge.example/mcp", token="t",
                                      transport=FakeMCPTransport())
        tools = client.list_tools()
        self.assertEqual(tools["count"], 3)
        self.assertIn("browser_open", tools["tools"])

    def test_call_tool_respects_allowlist(self):
        client = forge.ForgeMCPClient(endpoint="https://forge.example/mcp", token="t",
                                      allowed_tools=["browser_snapshot"], transport=FakeMCPTransport())
        with self.assertRaises(forge.ToolDeniedError):
            client.call_tool(name="browser_open")
        result = client.call_tool(name="browser_snapshot")
        self.assertEqual(result["tool"], "browser_snapshot")

    def test_write_tool_requires_host_approval(self):
        client = forge.ForgeMCPClient(endpoint="https://forge.example/mcp", token="t",
                                      transport=FakeMCPTransport())
        with self.assertRaises(forge.ToolDeniedError):
            client.call_tool(name="browser_click", arguments={"selector": "#go"})
        approved = client.call_tool(name="browser_click", arguments={"selector": "#go"},
                                    approval_reference="OWNER-APPROVED-1")
        self.assertTrue(approved["write_action"])
        self.assertEqual(approved["approval_reference"], "OWNER-APPROVED-1")

    def test_sse_responses_are_parsed(self):
        client = forge.ForgeMCPClient(endpoint="https://forge.example/mcp", token="t",
                                      transport=FakeMCPTransport(sse=True))
        tools = client.list_tools()
        self.assertEqual(tools["count"], 3)

    def test_protocol_error_is_raised(self):
        client = forge.ForgeMCPClient(endpoint="https://forge.example/mcp", token="t",
                                      transport=FakeMCPTransport(fail_method="tools/list"))
        with self.assertRaises(forge.ForgeMCPError):
            client.list_tools()

    def test_audit_log_records_requests_without_secrets(self):
        client = forge.ForgeMCPClient(endpoint="https://forge.example/mcp",
                                      token="forge-secret-token-value", transport=FakeMCPTransport())
        client.list_tools()
        audit = client.audit_log()
        self.assertTrue(audit)
        self.assertNotIn("forge-secret-token-value", json.dumps(audit))

    def test_results_are_redacted(self):
        class Leaky(FakeMCPTransport):
            def __call__(self, url, headers, body):
                message = json.loads(body.decode())
                return 200, json.dumps({"jsonrpc": "2.0", "id": message["id"],
                                        "result": {"content": [{"type": "text",
                                                                "text": "sk-" + "a" * 24}]}}).encode(), "application/json"

        client = forge.ForgeMCPClient(endpoint="https://forge.example/mcp", token="t", transport=Leaky())
        result = client.call_tool(name="browser_snapshot")
        self.assertNotIn("sk-", json.dumps(result))

    def test_direct_chatgpt_connector_is_blocked(self):
        caps = forge.ForgeMCPClient(endpoint="", token="").capabilities()
        self.assertEqual(caps["direct_chatgpt_connector"], "BLOCKED")
        self.assertEqual(caps["write_gate"], "explicit_host_approval_required")

    def test_reads_token_from_environment(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"FORGE_MCP_TOKEN": "env-token", "FORGE_MCP_ENDPOINT": "https://f/mcp"}):
            client = forge.ForgeMCPClient(transport=FakeMCPTransport())
            self.assertTrue(client.enabled)


if __name__ == "__main__":
    unittest.main()
