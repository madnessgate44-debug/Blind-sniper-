#!/usr/bin/env python3
"""Lease-gated bridge from the native task ledger to the browser adapter."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from blind_sniper_ledger import GitHubLedgerError, LedgerError
from blind_sniper_runtime import add_ledger_arguments, configure_ledger
from blind_sniper_browser import ACTIONS, BrowserAdapter, BrowserAdapterError, BrowserPolicyError


class BrowserDispatchError(RuntimeError):
    """A browser dispatch rejected by native task or lease policy."""


def dispatch_browser_action(
    *,
    ledger,
    task_id: str,
    owner_id: str,
    run_id: str,
    session_id: str,
    step_id: str,
    action: str,
    action_args: list[str],
    state_dir: str | Path,
    timeout: int = 45,
    approval_reference: str | None = None,
    adapter_factory: Callable[..., Any] = BrowserAdapter,
) -> dict[str, Any]:
    """Verify task state and lease, reserve the step, execute once, and ledger the receipt."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", task_id):
        raise BrowserDispatchError("Invalid task_id")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", owner_id):
        raise BrowserDispatchError("Invalid owner_id")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", run_id):
        raise BrowserDispatchError("Invalid run_id")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session_id):
        raise BrowserDispatchError("Invalid session_id")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", step_id):
        raise BrowserDispatchError("Invalid step_id")
    if action not in ACTIONS:
        raise BrowserDispatchError(f"Unsupported browser action: {action}")
    if not 1 <= timeout <= 120:
        raise BrowserDispatchError("timeout must be between 1 and 120 seconds")
    if not all(isinstance(value, str) and value for value in action_args):
        raise BrowserDispatchError("Browser action arguments must be non-empty strings")
    prefix = f"browser:{run_id}:{session_id}:{step_id}"
    started_key = f"{prefix}:started"
    completed_key = f"{prefix}:completed"
    reservation_payload = {
        "owner_id": owner_id, "run_id": run_id, "session_id": session_id,
        "step_id": step_id, "action": action,
    }
    try:
        # State, owner, lease budget and idempotency reservation are checked under
        # one local lock or one remote GitHub Contents compare-and-swap.
        ledger.reserve_browser_action_if_lease(
            task_id=task_id, owner_id=owner_id, payload=reservation_payload,
            idempotency_key=started_key, min_remaining_seconds=timeout + 10,
        )
    except LedgerError as exc:
        raise BrowserDispatchError(str(exc)) from exc

    # Recheck after the local lock / remote CAS round trip and immediately before
    # constructing the adapter. A lost lease leaves a reserved, non-replayable step.
    lease = ledger.lease_status(task_id)
    if not lease or lease.get("owner_id") != owner_id:
        raise BrowserDispatchError("Task lease was lost after reservation and before browser invocation")
    try:
        expires = datetime.fromisoformat(str(lease["lease_expires_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise BrowserDispatchError("Task lease expiry is missing or malformed") from exc
    if expires.tzinfo is None or (expires - datetime.now(timezone.utc)).total_seconds() <= timeout + 10:
        raise BrowserDispatchError("Task lease no longer has enough time before browser invocation")

    adapter = adapter_factory(
        task_id=task_id, run_id=run_id, session_id=session_id,
        state_dir=state_dir, approval_reference=approval_reference, timeout=timeout,
    )
    result = adapter.execute(action, step_id, *action_args)
    receipt = result.get("receipt")
    if not isinstance(receipt, dict):
        raise BrowserDispatchError("Browser adapter returned no structured action receipt")

    # Record the action result even if the lease expired while the bounded action ran.
    lease_after = ledger.lease_status(task_id)
    lease_valid_after = bool(lease_after and lease_after.get("owner_id") == owner_id)
    ledger.append(
        task_id=task_id,
        event_type="BROWSER_ACTION_COMPLETED",
        payload={
            "owner_id": owner_id, "run_id": run_id, "session_id": session_id,
            "step_id": step_id, "action": action, "exit_code": receipt.get("exit_code"),
            "receipt": receipt, "lease_valid_after_action": lease_valid_after,
        },
        idempotency_key=completed_key,
    )
    return {
        "task_id": task_id, "run_id": run_id, "session_id": session_id,
        "step_id": step_id, "action": action, "lease_valid_after_action": lease_valid_after,
        "receipt": receipt, "output": result.get("output", ""), "error": result.get("error", ""),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--owner-id", required=True, help="Host identity that owns the active native task lease")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--step-id", required=True)
    parser.add_argument("--action", required=True, choices=sorted({"open", "snapshot", "click", "fill", "press", "screenshot", "get-url", "close", "tabs", "tab-new", "tab-switch", "tab-close", "frame", "upload", "download", "pdf"}))
    parser.add_argument("--action-args-json", default="[]", help="JSON array of string arguments for the selected browser action")
    parser.add_argument("--state-dir", default=".blind-sniper/browser")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--approval-reference")
    add_ledger_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        action_args = json.loads(args.action_args_json)
        if not isinstance(action_args, list) or any(not isinstance(value, str) for value in action_args):
            raise BrowserDispatchError("--action-args-json must be a JSON array of strings")
        if not 1 <= args.timeout <= 120:
            raise BrowserDispatchError("--timeout must be between 1 and 120 seconds")
        ledger = configure_ledger(args)
        result = dispatch_browser_action(
            ledger=ledger, task_id=args.task_id, owner_id=args.owner_id,
            run_id=args.run_id, session_id=args.session_id, step_id=args.step_id,
            action=args.action, action_args=action_args, state_dir=args.state_dir,
            timeout=args.timeout, approval_reference=args.approval_reference,
        )
        print(json.dumps(result, sort_keys=True))
        return int(result["receipt"].get("exit_code", 1))
    except (BrowserDispatchError, BrowserAdapterError, BrowserPolicyError, GitHubLedgerError, LedgerError, OSError, ValueError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
