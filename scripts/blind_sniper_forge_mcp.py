#!/usr/bin/env python3
"""Forge MCP client adapter over Streamable HTTP (JSON-RPC 2.0).

Implements the Model Context Protocol client handshake and tool surface:

- ``initialize``       protocol negotiation
- ``notifications/initialized``  (sent after initialize)
- ``tools/list``       discover the server's tools
- ``tools/call``       invoke one allowlisted tool

Transport is Streamable HTTP: ``POST`` a JSON-RPC 2.0 message to the endpoint
with ``Accept: application/json, text/event-stream``. Servers may answer either
with a single JSON body or an SSE stream; both are parsed here.

Auth is a bearer token read from an environment variable (default
``FORGE_MCP_TOKEN``). The adapter is disabled without the token. Every request
and response is redacted before it reaches an audit receipt.

Browser *write* actions (click/type/press/upload/submit) are refused unless the
host passes an explicit approval reference. This adapter never claims that a
direct ChatGPT custom connector is available: this account is on a plan where
custom MCP connectors are gated, so the connector path stays BLOCKED and this
adapter is exercised server-to-server only.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from blind_sniper_redaction import redact_value

DEFAULT_PROTOCOL_VERSION = "2025-06-18"
DEFAULT_TIMEOUT_SECONDS = 30

# Tools that mutate remote browser/UI state and therefore need host approval.
WRITE_TOOL_MARKERS = ("click", "type", "fill", "press", "upload", "submit", "navigate", "open", "close")


class ForgeMCPError(RuntimeError):
    """Forge MCP transport, protocol or policy failure."""


class ToolDeniedError(ForgeMCPError):
    """A tool call was refused by the allowlist or the write-approval gate."""


def _is_write_tool(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in WRITE_TOOL_MARKERS)


class ForgeMCPClient:
    """Minimal, allowlisted MCP client with audit receipts and redaction."""

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        token: str | None = None,
        token_env: str = "FORGE_MCP_TOKEN",
        allowed_tools: list[str] | None = None,
        transport=None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        protocol_version: str = DEFAULT_PROTOCOL_VERSION,
    ) -> None:
        self.endpoint = (endpoint or os.environ.get("FORGE_MCP_ENDPOINT", "")).rstrip("/")
        self.token = token if token is not None else os.environ.get(token_env, "")
        self.token_env = token_env
        self.allowed_tools = list(allowed_tools or [])
        self.transport = transport or self._urlopen_transport
        if not 1 <= timeout <= 120:
            raise ForgeMCPError("timeout must be between 1 and 120 seconds")
        self.timeout = timeout
        self.protocol_version = protocol_version
        self._message_id = 0
        self._audit: list[dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        return bool(self.endpoint and self.token)

    def _next_id(self) -> int:
        self._message_id += 1
        return self._message_id

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.protocol_version,
            "User-Agent": "Blind-Sniper-Forge-MCP",
        }

    def _urlopen_transport(self, url: str, headers: dict, body: bytes):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.read(), response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), exc.headers.get("Content-Type", "") if exc.headers else ""
        except urllib.error.URLError as exc:
            raise ForgeMCPError(f"Forge MCP transport failed: {exc.reason}") from exc

    @staticmethod
    def _parse_sse(raw: bytes) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for block in raw.decode("utf-8", "replace").split("\n\n"):
            for line in block.splitlines():
                if line.startswith("data:"):
                    data = line[len("data:"):].strip()
                    if data:
                        try:
                            messages.append(json.loads(data))
                        except json.JSONDecodeError:
                            continue
        return messages

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if not self.enabled:
            raise ForgeMCPError(
                f"Forge MCP adapter is disabled: set FORGE_MCP_ENDPOINT and {self.token_env}"
            )
        message_id = self._next_id()
        body = json.dumps({
            "jsonrpc": "2.0", "id": message_id, "method": method, "params": params or {},
        }, separators=(",", ":")).encode("utf-8")
        status, raw, content_type = self.transport(self.endpoint, self._headers(), body)
        self._audit.append(redact_value({
            "direction": "request", "method": method, "id": message_id,
            "http_status": status, "content_type": content_type,
        }))
        if status != 200:
            raise ForgeMCPError(f"Forge MCP {method} failed with HTTP {status}")
        if "text/event-stream" in (content_type or ""):
            messages = self._parse_sse(raw)
            response = next((m for m in messages if m.get("id") == message_id), None)
        else:
            response = json.loads(raw.decode("utf-8"))
        if not isinstance(response, dict):
            raise ForgeMCPError(f"Forge MCP {method} returned no matching JSON-RPC response")
        if response.get("error"):
            raise ForgeMCPError(f"Forge MCP {method} error: {redact_value(response['error'])}")
        return response.get("result", {})

    # -- operations -----------------------------------------------------
    def initialize(self, *, client_name: str = "blind-sniper", client_version: str = "1.0.0") -> dict[str, Any]:
        result = self._rpc("initialize", {
            "protocolVersion": self.protocol_version,
            "capabilities": {"tools": {}},
            "clientInfo": {"name": client_name, "version": client_version},
        })
        # Best-effort initialized notification; servers may not require it.
        try:
            self._rpc("notifications/initialized", {})
        except ForgeMCPError:
            pass
        return redact_value({
            "protocol_version": result.get("protocolVersion"),
            "server_info": result.get("serverInfo"),
            "capabilities": result.get("capabilities"),
        })

    def list_tools(self) -> dict[str, Any]:
        result = self._rpc("tools/list", {})
        tools = result.get("tools", []) if isinstance(result, dict) else []
        names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
        return redact_value({"tools": names, "count": len(names), "raw": tools})

    def call_tool(
        self,
        *,
        name: str,
        arguments: dict[str, Any] | None = None,
        approval_reference: str | None = None,
    ) -> dict[str, Any]:
        if not name:
            raise ToolDeniedError("tool name is required")
        if self.allowed_tools and name not in self.allowed_tools:
            raise ToolDeniedError(f"tool {name} is not in the allowlist {self.allowed_tools}")
        if _is_write_tool(name) and not approval_reference:
            raise ToolDeniedError(f"tool {name} mutates remote state and requires an explicit host approval reference")
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        return redact_value({
            "tool": name, "result": result,
            "approval_reference": approval_reference,
            "write_action": _is_write_tool(name),
        })

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit)

    def capabilities(self) -> dict[str, Any]:
        return {
            "adapter": "forge_mcp_streamable_http",
            "enabled": self.enabled,
            "endpoint_configured": bool(self.endpoint),
            "secret_env": self.token_env,
            "operations": ["initialize", "tools/list", "tools/call"],
            "write_gate": "explicit_host_approval_required",
            "direct_chatgpt_connector": "BLOCKED",
            "connector_note": "Custom ChatGPT MCP connectors are plan-gated on this account; use server-to-server only.",
        }
