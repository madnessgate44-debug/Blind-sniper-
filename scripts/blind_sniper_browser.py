#!/usr/bin/env python3
"""Bounded adapter for the pinned agent-browser CLI.

The host supplies domain policy and any write approval through environment
variables. This module never invokes a shell and never persists page contents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = "1.0.0"
ACTIONS = {"open", "snapshot", "click", "fill", "press", "screenshot", "get-url", "close"}
MUTATING_ACTIONS = {"click", "fill", "press"}
SAFE_KEY_NAMES = {"ENTER", "TAB", "ESCAPE", "ARROWDOWN", "ARROWUP", "ARROWLEFT", "ARROWRIGHT"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class BrowserPolicyError(RuntimeError):
    pass


class BrowserAdapterError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise BrowserPolicyError(f"Invalid {label}")
    return value


def _domain_list(name: str) -> set[str]:
    return {item.strip().lower().rstrip(".") for item in os.environ.get(name, "").split(",") if item.strip()}


def _matches(host: str, rule: str) -> bool:
    return host == rule or host.endswith("." + rule)


def validate_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise BrowserPolicyError("Only absolute HTTP(S) URLs are permitted")
    if parsed.username is not None or parsed.password is not None:
        raise BrowserPolicyError("URLs containing embedded credentials are not permitted")
    host = parsed.hostname.lower().rstrip(".")
    blocked = _domain_list("BLIND_SNIPER_BROWSER_BLOCKED_DOMAINS")
    allowed = _domain_list("BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS")
    if any(_matches(host, rule) for rule in blocked):
        raise BrowserPolicyError(f"Domain is blocked by host policy: {host}")
    if not allowed or not any(_matches(host, rule) for rule in allowed):
        raise BrowserPolicyError(f"Domain is not in the host allowlist: {host}")
    return host


class BrowserAdapter:
    def __init__(
        self, *, task_id: str, run_id: str, session_id: str,
        state_dir: str | Path = ".blind-sniper/browser",
        approval_reference: str | None = None, timeout: int = 45,
        binary: str | None = None,
    ) -> None:
        self.task_id = _safe_id(task_id, "task_id")
        self.run_id = _safe_id(run_id, "run_id")
        if not SESSION_ID.fullmatch(session_id):
            raise BrowserPolicyError("Invalid session_id")
        if not 1 <= timeout <= 120:
            raise BrowserPolicyError("timeout must be between 1 and 120 seconds")
        self.session_id = session_id
        self.approval_reference = approval_reference
        self.timeout = timeout
        self.binary = binary or os.environ.get("AGENT_BROWSER_BIN", "agent-browser")
        self.state_dir = Path(state_dir).resolve()
        self.sessions_dir = self.state_dir / "sessions"
        self.receipts_dir = self.state_dir / "receipts"
        self.artifacts_dir = self.state_dir / "artifacts"
        for directory in (self.sessions_dir, self.receipts_dir, self.artifacts_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self.session_file = self.sessions_dir / f"{session_id}.json"
        self.receipt_file = self.receipts_dir / f"{self.task_id}__{self.run_id}.jsonl"
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if not self.session_file.exists():
            return {
                "schema_version": SCHEMA_VERSION, "task_id": self.task_id,
                "run_id": self.run_id, "session_id": self.session_id,
                "status": "NEW", "current_url": None, "created_at": utc_now(),
            }
        try:
            state = json.loads(self.session_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BrowserAdapterError(f"Cannot recover session metadata: {exc}") from exc
        for key, expected in (("task_id", self.task_id), ("run_id", self.run_id), ("session_id", self.session_id)):
            if state.get(key) != expected:
                raise BrowserPolicyError(f"Session {key} mismatch; refusing cross-task reuse")
        if state.get("status") == "CLOSED":
            raise BrowserPolicyError("Session is closed; create a new session_id")
        return state

    def _save_state(self) -> None:
        temp = self.session_file.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, self.session_file)

    def _command(self, *args: str) -> tuple[int, str, str, list[str]]:
        command = [self.binary, "--session", self.session_id, "--json", *args]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout, check=False, shell=False)
        except FileNotFoundError as exc:
            raise BrowserAdapterError("agent-browser is not installed; install the pinned CLI and Chromium on the execution host") from exc
        except subprocess.TimeoutExpired as exc:
            raise BrowserAdapterError(f"Browser command exceeded {self.timeout}s timeout") from exc
        return completed.returncode, completed.stdout, completed.stderr, command

    def _assert_write_approved(self) -> None:
        if os.environ.get("BLIND_SNIPER_BROWSER_WRITE_APPROVED") != "1":
            raise BrowserPolicyError("Mutating browser action blocked: host write approval is absent")
        if not self.approval_reference:
            raise BrowserPolicyError("Mutating browser action requires a host approval reference")

    def _current_url(self) -> str | None:
        code, stdout, _, _ = self._command("get", "url")
        if code != 0:
            return self.state.get("current_url")
        try:
            data = json.loads(stdout)
            pending = [data]
            while pending:
                item = pending.pop()
                if isinstance(item, dict):
                    for key, value in item.items():
                        if key.lower() in {"url", "value"} and isinstance(value, str) and value.startswith(("http://", "https://")):
                            return value
                        pending.append(value)
                elif isinstance(item, list):
                    pending.extend(item)
        except json.JSONDecodeError:
            pass
        match = re.search(r"https?://[^\s\"']+", stdout)
        return match.group(0) if match else self.state.get("current_url")

    def _ensure_step_unused(self, step_id: str) -> None:
        if not self.receipt_file.exists():
            return
        for line in self.receipt_file.read_text(encoding="utf-8").splitlines():
            try:
                prior = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BrowserAdapterError("Receipt ledger is corrupt; refusing to append") from exc
            if prior.get("step_id") == step_id:
                raise BrowserPolicyError("Duplicate step_id; refusing to replay an action")

    def _append_receipt(self, receipt: dict[str, Any]) -> None:
        self._ensure_step_unused(receipt["step_id"])
        with self.receipt_file.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, sort_keys=True) + "\n")

    def execute(self, action: str, step_id: str, *args: str) -> dict[str, Any]:
        if action not in ACTIONS:
            raise BrowserPolicyError(f"Unsupported browser action: {action}")
        _safe_id(step_id, "step_id")
        self._ensure_step_unused(step_id)
        started = utc_now()
        requested_url = None
        artifact_paths: list[str] = []

        if action == "open":
            if len(args) != 1:
                raise BrowserPolicyError("open requires exactly one URL")
            validate_url(args[0])
            requested_url = args[0]
            self.state["current_url"] = requested_url
            cli_args = ["open", args[0]]
        elif action == "snapshot":
            if args:
                raise BrowserPolicyError("snapshot takes no arguments")
            validate_url(self.state.get("current_url") or "")
            cli_args = ["snapshot"]
        elif action == "click":
            self._assert_write_approved()
            if len(args) != 1:
                raise BrowserPolicyError("click requires one selector")
            validate_url(self.state.get("current_url") or "")
            cli_args = ["click", args[0]]
        elif action == "fill":
            self._assert_write_approved()
            if len(args) != 2:
                raise BrowserPolicyError("fill requires a selector and value")
            validate_url(self.state.get("current_url") or "")
            if re.search(r"password|passwd|secret|token|api[_-]?key|otp|one.?time.?code", args[0], re.I):
                raise BrowserPolicyError("Sensitive credential selectors are not supported")
            cli_args = ["fill", args[0], args[1]]
        elif action == "press":
            self._assert_write_approved()
            if len(args) != 1 or args[0].upper() not in SAFE_KEY_NAMES:
                raise BrowserPolicyError("press accepts only a supported navigation key")
            validate_url(self.state.get("current_url") or "")
            cli_args = ["press", args[0]]
        elif action == "screenshot":
            validate_url(self.state.get("current_url") or "")
            if len(args) != 1 or Path(args[0]).name != args[0] or args[0] in {"", ".", ".."}:
                raise BrowserPolicyError("screenshot requires a simple filename")
            target = (self.artifacts_dir / args[0]).resolve()
            if self.artifacts_dir not in target.parents:
                raise BrowserPolicyError("Screenshot path escapes the artifact directory")
            cli_args = ["screenshot", str(target)]
            artifact_paths.append(str(target))
        elif action == "get-url":
            cli_args = ["get", "url"]
        else:
            cli_args = ["close"]

        if action not in {"open", "get-url", "close"}:
            requested_url = self.state.get("current_url")
        code, stdout, stderr, command = self._command(*cli_args)
        observed_url = requested_url
        policy_error = None
        if action == "open":
            self.state["status"] = "OPEN"
        if action == "open" or action in MUTATING_ACTIONS or action == "get-url":
            observed_url = self._current_url()
            if observed_url:
                try:
                    validate_url(observed_url)
                    self.state["current_url"] = observed_url
                except BrowserPolicyError as exc:
                    policy_error = str(exc)
                    self._command("close")
                    self.state["status"] = "CLOSED"
                    self.state["closed_at"] = utc_now()
                    code = 2
                    stderr = (stderr + "\n" + policy_error).strip()
        elif action == "close":
            self.state["status"] = "CLOSED"
            self.state["closed_at"] = utc_now()

        receipt = {
            "schema_version": SCHEMA_VERSION, "task_id": self.task_id,
            "run_id": self.run_id, "session_id": self.session_id,
            "step_id": step_id, "action": action,
            "approval_reference": self.approval_reference if action in MUTATING_ACTIONS else None,
            "requested_url": requested_url, "observed_url": observed_url,
            "started_at": started, "completed_at": utc_now(),
            "command": [("[REDACTED]" if action == "fill" and i == len(command) - 1 else value) for i, value in enumerate(command)],
            "exit_code": code,
            "stdout_bytes": len(stdout.encode("utf-8")),
            "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            "stderr_bytes": len(stderr.encode("utf-8")),
            "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
            "artifact_paths": artifact_paths,
            "policy_error": policy_error,
        }
        self.state["last_step_id"] = step_id
        self.state["last_action"] = action
        self.state["updated_at"] = receipt["completed_at"]
        self._save_state()
        self._append_receipt(receipt)
        result = {"receipt": receipt, "output": stdout, "error": stderr}
        if code != 0:
            result["error"] = stderr or f"agent-browser exited with code {code}"
        return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--step-id", required=True)
    parser.add_argument("--state-dir", default=".blind-sniper/browser")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--approval-reference")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("open").add_argument("url")
    for name in ("snapshot", "get-url", "close"):
        sub.add_parser(name)
    sub.add_parser("click").add_argument("selector")
    fill = sub.add_parser("fill")
    fill.add_argument("selector")
    fill.add_argument("value")
    sub.add_parser("press").add_argument("key")
    sub.add_parser("screenshot").add_argument("filename")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    adapter = BrowserAdapter(
        task_id=args.task_id, run_id=args.run_id, session_id=args.session_id,
        state_dir=args.state_dir, approval_reference=args.approval_reference,
        timeout=args.timeout,
    )
    action_args: tuple[str, ...] = ()
    if args.action == "open":
        action_args = (args.url,)
    elif args.action == "click":
        action_args = (args.selector,)
    elif args.action == "fill":
        action_args = (args.selector, args.value)
    elif args.action == "press":
        action_args = (args.key,)
    elif args.action == "screenshot":
        action_args = (args.filename,)
    try:
        result = adapter.execute(args.action, args.step_id, *action_args)
    except (BrowserPolicyError, BrowserAdapterError) as exc:
        print(json.dumps({"error": str(exc), "action": args.action, "step_id": args.step_id}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return int(result["receipt"]["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
