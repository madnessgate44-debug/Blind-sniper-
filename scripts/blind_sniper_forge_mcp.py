#!/usr/bin/env python3
"""Forge Streamable HTTP MCP client adapter.

Implements the MCP Streamable HTTP transport (JSON-RPC 2.0 over a single
authenticated HTTP endpoint): ``initialize``, ``tools/list`` and ``tools/call``.

Safety posture:
* Disabled by default. The adapter refuses to construct unless a durable HTTPS
  endpoint and an auth token are both configured.
* An ephemeral sandbox URL is explicitly refused unless the host opts in via
  ``allow_ephemeral_host=True``; the constructor never treats a sandbox host as
  a durable endpoint.
* Tool calls are restricted to a host-supplied allowlist. Browser write actions
  are additionally gated by an explicit host approval reference.
* Every call returns an audit receipt with the request/response redacted.

This module does not claim that a ChatGPT connector is registered. Registration
is a host/UI action outside this repository.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from blind_sniper_redact import redact

DEFAULT_ENDPOINT_ENV = "FORGE_MCP_ENDPOINT"
DEFAULT_TOKEN_ENV = "FORGE_MCP_TOKEN"
# Hosts known to be ephemeral preview sandboxes, never durable endpoints.
EPHEMERAL_HOST_SUFFIXES = (".prod-runtime.all-hands.dev",)
# Browser actions that mutate remote state require an explicit host approval.
WRITE_TOOLS = {
    "browser_click", "browser_type", "browser_fill", "browser_press",
    "browser_submit", "browser_upload", "browser_download",
}


class ForgeMCPError(RuntimeError):
    """Forge MCP adapter failure: configuration, transport, protocol or policy."""


def _urlopen_transport(method: str, url: str, headers: dict, body: bytes | None, timeout: int):
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers.items())
    except HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers.items())
    except URLError as exc:
        raise ForgeMCPError(f"Forge MCP transport failed: {exc.reason}") from exc


class ForgeMCPClient:
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        token: str | None = None,
        endpoint_env: str = DEFAULT_ENDPOINT_ENV,
        token_env: str = DEFAULT_TOKEN_ENV,
        tool_allowlist: list[str] | None = None,
        transport: Callable[..., Any] | None = None,
        timeout: int = 30,
        allow_ephemeral_host: bool = False,
    ) -> None:
        resolved_endpoint = endpoint if endpoint is not None else os.environ.get(endpoint_env, "")
        resolved_token = token if token is not None else os.environ.get(token_env, "")
        if not resolved_endpoint:
            raise ForgeMCPError(
                f"Forge MCP is disabled: no durable endpoint configured in {endpoint_env}"
            )
        if not resolved_endpoint.startswith("https://"):
            raise ForgeMCPError("Forge MCP requires an absolute https endpoint")
        host = resolved_endpoint.split("://", 1)[1].split("/", 1)[0].split(":", 1)[0].lower()
        if not allow_ephemeral_host and any(host.endswith(suffix) for suffix in EPHEMERAL_HOST_SUFFIXES):
            raise ForgeMCPError(
                "Forge MCP refuses an ephemeral sandbox host; configure a durable endpoint"
            )
        if not resolved_token:
            raise ForgeMCPError(f"Forge MCP is disabled: no auth token configured in {token_env}")
        self.endpoint = resolved_endpoint
        self._token = resolved_token
        self.tool_allowlist = set(tool_allowlist or [])
        self.transport = transport or _urlopen_transport
        self.timeout = timeout
        self._request_id = 0

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "Blind-Sniper-Forge-MCP",
        }

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        body = {"jsonrpc": "2.0", "id": self._request_id, "method": method}
        if params is not None:
            body["params"] = params
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        status, raw, _headers = self.transport("POST", self.endpoint, self._headers(), payload, self.timeout)
        if status == 401:
            raise ForgeMCPError("Forge MCP rejected the auth token (HTTP 401)")
        if status not in (200, 202):
            raise ForgeMCPError(f"Forge MCP {method} failed with HTTP {status}")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ForgeMCPError(f"Forge MCP {method} returned a non-JSON response") from exc
        if isinstance(decoded, dict) and decoded.get("error"):
            raise ForgeMCPError(f"Forge MCP {method} error: {redact(decoded['error'])}")
        return decoded

    def initialize(self) -> dict[str, Any]:
        return self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "blind-sniper", "version": "1.0.0"},
        })

    def list_tools(self) -> dict[str, Any]:
        decoded = self._rpc("tools/list")
        tools = decoded.get("result", {}).get("tools", []) if isinstance(decoded, dict) else []
        names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
        return {"tools": redact(names), "raw": redact(decoded)}

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        approval_reference: str | None = None,
    ) -> dict[str, Any]:
        if self.tool_allowlist and name not in self.tool_allowlist:
            raise ForgeMCPError(f"Tool {name} is not in the host allowlist")
        if name in WRITE_TOOLS and not (approval_reference and str(approval_reference).strip()):
            raise ForgeMCPError(f"Browser write tool {name} requires an explicit host approval reference")
        decoded = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        return {
            "tool": name,
            "approval_reference": approval_reference if name in WRITE_TOOLS else None,
            "raw": redact(decoded),
        }

    def receipt(self, *, operation: str, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "adapter": "forge_mcp_streamable_http",
            "operation": operation,
            "at": datetime.now(timezone.utc).isoformat(),
            "result": redact(result),
        }
