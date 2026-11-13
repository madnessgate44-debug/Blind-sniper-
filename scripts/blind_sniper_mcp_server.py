#!/usr/bin/env python3
"""Blind Sniper native MCP stdio server for its lease-gated browser.

Run from the repository root:
  python scripts/blind_sniper_mcp_server.py

The server speaks newline-delimited JSON-RPC over stdio (MCP stdio transport).
It owns browser task/session IDs internally. Browser policy, host approval,
lease checks, idempotency reservations and receipts remain in native modules.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_browser import ACTIONS, BrowserAdapterError, BrowserPolicyError  # noqa: E402
from blind_sniper_browser_dispatch import BrowserDispatchError, dispatch_browser_action  # noqa: E402
from blind_sniper_ledger import LedgerError, TaskLedger  # noqa: E402
from blind_sniper_runtime import build_plan, create_task_state  # noqa: E402

PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {"name": "blind-sniper-native-browser", "version": "0.1.0"}
OWNER_ID = os.environ.get("BLIND_SNIPER_MCP_OWNER_ID", "blind-sniper-mcp-host")
LEASE_SECONDS = 3600
MAX_MESSAGE_BYTES = 1_048_576
MUTATING = {"click", "fill", "press", "upload", "clipboard-write", "clipboard-copy", "clipboard-paste"}


def _text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class BrowserMCP:
    def __init__(self) -> None:
        default_root = Path(os.environ.get("BLIND_SNIPER_MCP_STATE_DIR", "/tmp/blind-sniper-mcp")).resolve()
        try:
            default_root.relative_to(ROOT)
        except ValueError:
            pass
        else:
            raise RuntimeError("MCP private state directory must be outside the public repository")
        default_root.mkdir(parents=True, exist_ok=True)
        self.state_root = default_root
        ledger_path = Path(os.environ.get(
            "BLIND_SNIPER_MCP_LEDGER", str(default_root / "events.jsonl")
        )).resolve()
        browser_state = Path(os.environ.get(
            "BLIND_SNIPER_BROWSER_STATE_DIR", str(default_root / "browser")
        )).resolve()
        for label, candidate in (("ledger", ledger_path), ("browser state", browser_state)):
            try:
                candidate.relative_to(ROOT)
            except ValueError:
                pass
            else:
                raise RuntimeError(f"Private {label} path must be outside the public repository")
        self.ledger = TaskLedger(ledger_path)
        self.browser_state = browser_state
        self.active: dict[str, str] | None = None

    def _lease(self, task_id: str, key: str) -> None:
        claim = self.ledger.claim_task(
            task_id=task_id, owner_id=OWNER_ID, lease_seconds=LEASE_SECONDS,
            idempotency_key=f"{task_id}:mcp-lease:{key}",
        )
        if not claim.get("claimed"):
            raise RuntimeError("Browser task lease is held by another owner or is unavailable")

    def _dispatch(self, action: str, args: list[str]) -> dict[str, Any]:
        if not self.active:
            raise RuntimeError("No active browser session; call browser.start or browser.resume")
        row = self.active
        self._lease(row["task_id"], uuid.uuid4().hex)
        return dispatch_browser_action(
            ledger=self.ledger, task_id=row["task_id"], owner_id=OWNER_ID,
            run_id=row["run_id"], session_id=row["session_id"],
            step_id=uuid.uuid4().hex, action=action, action_args=args,
            state_dir=self.browser_state,
            approval_reference=os.environ.get("BLIND_SNIPER_BROWSER_APPROVAL_REFERENCE"),
            timeout=45,
        )

    def start(self, url: str) -> dict[str, Any]:
        if self.active:
            raise RuntimeError("A browser session is already active; close or resume it first")
        task_id = "BS-MCP-" + uuid.uuid4().hex
        run_id = uuid.uuid4().hex
        session_id = uuid.uuid4().hex[:24]
        plan = build_plan({
            "task_id": task_id,
            "objective": "Conversational native browser session",
            "task_type": "browser",
            "requested_actions": ["read"],
        }, ROOT)
        state = create_task_state(plan)
        self.ledger.append(
            task_id=task_id, event_type="TASK_TRANSITIONED",
            payload={"state": state},
            idempotency_key=f"{task_id}:mcp-created",
        )
        self._lease(task_id, "initial")
        state["status"] = "EXECUTING"
        state["implementer_id"] = OWNER_ID
        self.ledger.append_transition_if_lease(
            task_id=task_id, owner_id=OWNER_ID,
            payload={"state": state, "lease_guard": {
                "task_id": task_id, "status": "EXECUTING", "implementer_id": OWNER_ID,
            }},
            idempotency_key=f"{task_id}:mcp-executing",
        )
        self.active = {"task_id": task_id, "run_id": run_id, "session_id": session_id}
        result = self._dispatch("open", [url])
        return {"session": dict(self.active), "browser": result}

    def resume(self, task_id: str, run_id: str, session_id: str) -> dict[str, Any]:
        if self.active:
            raise RuntimeError("A browser session is already active")
        lease = self.ledger.lease_status(task_id)
        if not lease or lease.get("owner_id") != OWNER_ID:
            raise RuntimeError("No active native lease for that browser session")
        self.active = {"task_id": task_id, "run_id": run_id, "session_id": session_id}
        result = self._dispatch("snapshot", [])
        return {"session": dict(self.active), "browser": result}

    def action(self, action: str, args: list[str]) -> dict[str, Any]:
        if action not in ACTIONS - {"close"}:
            raise ValueError(f"Unsupported browser action: {action}; use browser.close for session shutdown")
        if action in MUTATING:
            if os.environ.get("BLIND_SNIPER_BROWSER_WRITE_APPROVED") != "1":
                raise PermissionError("Host browser-write approval is absent")
            if not os.environ.get("BLIND_SNIPER_BROWSER_APPROVAL_REFERENCE"):
                raise PermissionError("Host browser approval reference is absent")
        return self._dispatch(action, args)

    def status(self) -> dict[str, Any]:
        url = self._dispatch("get-url", [])
        snapshot = self._dispatch("snapshot", [])
        screenshot = self._dispatch("screenshot", [f"browser-{uuid.uuid4().hex}.png"])
        return {
            "url": url.get("output", ""),
            "visible_text": snapshot.get("output", ""),
            "screenshot_reference": screenshot.get("receipt", {}).get("artifact_paths", []),
            "receipts": [url.get("receipt"), snapshot.get("receipt"), screenshot.get("receipt")],
        }

    def close(self) -> dict[str, Any]:
        if not self.active:
            raise RuntimeError("No active browser session")
        row = self.active
        result = self._dispatch("close", [])
        if int(result.get("receipt", {}).get("exit_code", 1)) != 0:
            return {"browser": result, "lease_released": False}
        released = self.ledger.release_task(
            task_id=row["task_id"], owner_id=OWNER_ID,
            idempotency_key=f"{row['task_id']}:mcp-release",
        )
        self.active = None
        return {"browser": result, "lease_released": bool(released.get("released"))}


TOOLS = [
    {
        "name": "browser.start",
        "description": "Create a native leased browser task and open one HTTP(S) URL subject to host browser policy.",
        "inputSchema": {"type": "object", "properties": {"url": {"type": "string", "minLength": 8, "maxLength": 2048}}, "required": ["url"], "additionalProperties": False},
    },
    {
        "name": "browser.resume",
        "description": "Resume a browser session by its returned task, run and session IDs when its native lease and local browser state still exist.",
        "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "run_id": {"type": "string"}, "session_id": {"type": "string"}}, "required": ["task_id", "run_id", "session_id"], "additionalProperties": False},
    },
    {
        "name": "browser.action",
        "description": "Execute one registered native browser action. Mutating actions require host approval. Arguments are strings in the adapter's documented order.",
        "inputSchema": {"type": "object", "properties": {"action": {"type": "string", "enum": sorted(ACTIONS - {"close"})}, "args": {"type": "array", "items": {"type": "string"}, "maxItems": 3}}, "required": ["action"], "additionalProperties": False},
    },
    {
        "name": "browser.status",
        "description": "Return current URL, accessibility/visible page snapshot and a private screenshot artifact reference.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "browser.close",
        "description": "Close the current native browser session and release its task lease.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def _has_failed_receipt(value: Any) -> bool:
    if isinstance(value, dict):
        receipt = value.get("receipt")
        if isinstance(receipt, dict) and receipt.get("exit_code") not in (None, 0):
            return True
        return any(_has_failed_receipt(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_failed_receipt(item) for item in value)
    return False


def _result(value: Any) -> dict[str, Any]:
    failed = _has_failed_receipt(value)
    result = {"content": [{"type": "text", "text": _text(value)}], "structuredContent": value}
    if failed:
        result["isError"] = True
    return result


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def handle(server: BrowserMCP, message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    if not isinstance(params, dict):
        if request_id is None:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "params must be an object"}}
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
            "instructions": "Use browser.start first. The host controls URL allowlists and all write approvals. CAPTCHA/MFA and credentials must be handled by the user.",
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "arguments must be an object"}}
        try:
            if name == "browser.start":
                value = server.start(str(arguments["url"]))
            elif name == "browser.resume":
                value = server.resume(str(arguments["task_id"]), str(arguments["run_id"]), str(arguments["session_id"]))
            elif name == "browser.action":
                action = str(arguments["action"])
                args = arguments.get("args", [])
                if not isinstance(args, list) or any(not isinstance(x, str) for x in args):
                    raise ValueError("args must be an array of strings")
                value = server.action(action, args)
            elif name == "browser.status":
                value = server.status()
            elif name == "browser.close":
                value = server.close()
            else:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "Unknown tool"}}
            return {"jsonrpc": "2.0", "id": request_id, "result": _result(value)}
        except (KeyError, TypeError, ValueError, RuntimeError, PermissionError,
                BrowserDispatchError, BrowserAdapterError, BrowserPolicyError, LedgerError, OSError) as exc:
            return {"jsonrpc": "2.0", "id": request_id, "result": _error(f"{type(exc).__name__}: {exc}")}
    if request_id is None:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}


def main() -> int:
    server = BrowserMCP()
    while True:
        raw = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 1)
        if not raw:
            return 0
        if len(raw) > MAX_MESSAGE_BYTES:
            print(_text({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Message too large"}}), flush=True)
            return 2
        try:
            message = json.loads(raw)
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                raise ValueError("Invalid JSON-RPC message")
            response = handle(server, message)
        except (json.JSONDecodeError, ValueError) as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        if response is not None:
            sys.stdout.write(_text(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
