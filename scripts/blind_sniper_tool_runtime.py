#!/usr/bin/env python3
"""Blind Sniper's task-scoped native tool registry and executor.

Tools are static, allowlisted operations. No shell string, dynamic import, plugin
handoff or external agent is accepted. Every side effect is reserved against the
current durable task lease before execution and receives a correlated ledger event.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from blind_sniper_redact import redact, redact_text
from blind_sniper_browser import BrowserAdapter

ROOT = Path(__file__).resolve().parents[1]
MAX_READ_BYTES = 256_000
MAX_WRITE_BYTES = 128_000
MAX_TOOL_OUTPUT_CHARS = 8_000
MAX_COMMAND_TIMEOUT = 600

TOOL_DEFINITIONS = {
    "repo.read_file": {
        "type": "function",
        "function": {
            "name": "repo.read_file",
            "description": "Read one UTF-8 text file inside the authorized workspace and allowed paths.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "minLength": 1, "maxLength": 512}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    "repo.write_file": {
        "type": "function",
        "function": {
            "name": "repo.write_file",
            "description": "Replace one explicitly allowlisted workspace file. Requires workspace_write permission.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1, "maxLength": 512},
                    "content": {"type": "string", "maxLength": MAX_WRITE_BYTES},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    "verification.run": {
        "type": "function",
        "function": {
            "name": "verification.run",
            "description": "Run one fixed, read-only verification command from the native command allowlist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command_id": {"type": "string", "enum": ["runtime-validator", "unit-tests"]},
                },
                "required": ["command_id"],
                "additionalProperties": False,
            },
        },
    },
    "browser.navigate": {
        "type": "function",
        "function": {
            "name": "browser.navigate",
            "description": "Navigate the task-scoped native Chromium session to a host-allowlisted HTTP(S) URL.",
            "parameters": {"type": "object", "properties": {"url": {"type": "string", "minLength": 8, "maxLength": 2048}}, "required": ["url"], "additionalProperties": False},
        },
    },
    "browser.snapshot": {
        "type": "function",
        "function": {
            "name": "browser.snapshot",
            "description": "Read an accessibility snapshot from the current task-scoped browser page.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    "browser.get_url": {
        "type": "function",
        "function": {
            "name": "browser.get_url",
            "description": "Read the current URL of the task-scoped browser session.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    "browser.tabs": {
        "type": "function",
        "function": {
            "name": "browser.tabs",
            "description": "List tabs in the current task-scoped browser session.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    "browser.click": {
        "type": "function",
        "function": {
            "name": "browser.click",
            "description": "Click one selector in the task browser; requires host-approved browser write permission.",
            "parameters": {"type": "object", "properties": {"selector": {"type": "string", "minLength": 1, "maxLength": 256}}, "required": ["selector"], "additionalProperties": False},
        },
    },
    "browser.fill": {
        "type": "function",
        "function": {
            "name": "browser.fill",
            "description": "Fill one non-sensitive selector in the task browser; requires host-approved browser write permission.",
            "parameters": {"type": "object", "properties": {"selector": {"type": "string", "minLength": 1, "maxLength": 256}, "value": {"type": "string", "maxLength": 4000}}, "required": ["selector", "value"], "additionalProperties": False},
        },
    },
    "browser.press": {
        "type": "function",
        "function": {
            "name": "browser.press",
            "description": "Press one supported navigation key in the task browser; requires host-approved browser write permission.",
            "parameters": {"type": "object", "properties": {"key": {"type": "string", "enum": ["ENTER", "TAB", "ESC", "ESCAPE", "ARROWDOWN", "ARROWUP", "ARROWLEFT", "ARROWRIGHT"]}}, "required": ["key"], "additionalProperties": False},
        },
    },
    "browser.screenshot": {
        "type": "function",
        "function": {
            "name": "browser.screenshot",
            "description": "Capture a screenshot to the private task browser artifact directory.",
            "parameters": {"type": "object", "properties": {"filename": {"type": "string", "minLength": 1, "maxLength": 128}}, "required": ["filename"], "additionalProperties": False},
        },
    },
}

COMMANDS = {
    "runtime-validator": [sys.executable, "scripts/validate_blind_sniper_runtime.py"],
    "unit-tests": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
}
FORBIDDEN_WRITE_PATHS = {
    "AGENTS.md",
    "ENGINEERING_EXECUTION_OS.md",
    "chatgpt-home/AUTHORITY_DELEGATION.md",
    "chatgpt-home/BLIND_SNIPER.md",
    "chatgpt-home/BLIND_SNIPER_OS.md",
    "chatgpt-home/runtime/authority.json",
}
FORBIDDEN_WRITE_PREFIXES = (".github/", "chatgpt-home/runtime/")


class NativeToolError(RuntimeError):
    """Task-scoped native tool policy or execution failure."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


class NativeToolRuntime:
    """Execute only registered tools under a live task lease and explicit scope."""

    def __init__(
        self,
        queue: Any,
        *,
        workspace_root: Path = ROOT,
        command_timeout: int = MAX_COMMAND_TIMEOUT,
        browser_state_dir: Path | None = None,
        browser_adapter_factory: Any = BrowserAdapter,
    ) -> None:
        if not hasattr(queue, "reserve_tool_call") or not hasattr(queue, "complete_tool_call"):
            raise NativeToolError("Native tool runtime requires durable lease-bound tool receipts")
        if not 1 <= command_timeout <= MAX_COMMAND_TIMEOUT:
            raise NativeToolError("command_timeout must be between 1 and 600 seconds")
        self.queue = queue
        self.workspace_root = workspace_root.resolve()
        self.command_timeout = command_timeout
        self.browser_state_dir = (browser_state_dir or Path(tempfile.gettempdir()) / "blind-sniper-browser-state").resolve()
        try:
            self.browser_state_dir.relative_to(self.workspace_root)
        except ValueError:
            pass
        else:
            raise NativeToolError("Browser state/artifacts must remain outside the public repository workspace")
        self.browser_adapter_factory = browser_adapter_factory

    @staticmethod
    def definitions(allowlist: tuple[str, ...] | list[str]) -> list[dict[str, Any]]:
        unknown = set(allowlist) - set(TOOL_DEFINITIONS)
        if unknown:
            raise NativeToolError(f"Tool allowlist contains unregistered tools: {sorted(unknown)}")
        return [TOOL_DEFINITIONS[name] for name in allowlist]

    @staticmethod
    def validate_spec(spec: Any) -> None:
        NativeToolRuntime.definitions(spec.tool_allowlist)
        if "repo.write_file" in spec.tool_allowlist:
            if spec.permission_profile != "workspace_write":
                raise NativeToolError("repo.write_file requires workspace_write permission")
            if not spec.allowed_paths:
                raise NativeToolError("repo.write_file requires explicit exact allowed_paths")
        if any(name.startswith("repo.") for name in spec.tool_allowlist) and not spec.allowed_paths:
            raise NativeToolError("Repository tools require explicit allowed_paths")
        browser_write_tools = {"browser.click", "browser.fill", "browser.press"} & set(spec.tool_allowlist)
        if browser_write_tools:
            if spec.permission_profile != "workspace_write":
                raise NativeToolError("Mutating browser tools require workspace_write permission")
            if not spec.browser_approval_reference.strip():
                raise NativeToolError("Mutating browser tools require a host approval reference")
            if os.environ.get("BLIND_SNIPER_BROWSER_WRITE_APPROVED") != "1":
                raise NativeToolError("Mutating browser tools require host BLIND_SNIPER_BROWSER_WRITE_APPROVED=1")

    def _workspace_path(self, raw: str, spec: Any, *, write: bool) -> tuple[Path, str]:
        if not isinstance(raw, str) or not raw.strip() or "\\" in raw:
            raise NativeToolError("Tool path must be a non-empty repository-relative POSIX path")
        relative = PurePosixPath(raw)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise NativeToolError("Absolute, dot and parent traversal paths are forbidden")
        normalized = relative.as_posix()
        if not any(
            normalized == allowed or (not write and allowed.endswith("/") and normalized.startswith(allowed))
            for allowed in spec.allowed_paths
        ):
            raise NativeToolError("Path is outside the task's allowed_paths")
        if any(part == ".git" or part.startswith(".env") or part in {"secrets", ".ssh"} for part in relative.parts):
            raise NativeToolError("Sensitive or repository-internal paths are forbidden")
        if write and (
            normalized in FORBIDDEN_WRITE_PATHS
            or any(normalized.startswith(prefix) for prefix in FORBIDDEN_WRITE_PREFIXES)
        ):
            raise NativeToolError("Policy/authority and workflow configuration files are not writable by model tools")
        candidate = self.workspace_root.joinpath(*relative.parts)
        cursor = self.workspace_root
        for part in relative.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise NativeToolError("Symlink traversal is forbidden")
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise NativeToolError("Tool path escapes the workspace root") from exc
        return resolved, normalized

    def _read_file(self, arguments: dict[str, Any], spec: Any) -> dict[str, Any]:
        path, normalized = self._workspace_path(arguments.get("path"), spec, write=False)
        if not path.is_file():
            raise NativeToolError("Requested path is not a regular file")
        raw = path.read_bytes()
        if len(raw) > MAX_READ_BYTES:
            raise NativeToolError(f"File exceeds the {MAX_READ_BYTES}-byte read limit")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NativeToolError("Only UTF-8 text files are readable through this tool") from exc
        return {
            "path": normalized,
            "content": redact_text(content)[:MAX_TOOL_OUTPUT_CHARS],
            "sha256": hashlib.sha256(raw).hexdigest(),
            "truncated": len(content) > MAX_TOOL_OUTPUT_CHARS,
        }

    def _write_file(self, arguments: dict[str, Any], spec: Any) -> dict[str, Any]:
        if spec.permission_profile != "workspace_write":
            raise NativeToolError("Workspace writes require workspace_write permission")
        path, normalized = self._workspace_path(arguments.get("path"), spec, write=True)
        content = arguments.get("content")
        if not isinstance(content, str):
            raise NativeToolError("File content must be a string")
        raw = content.encode("utf-8")
        if len(raw) > MAX_WRITE_BYTES:
            raise NativeToolError(f"File exceeds the {MAX_WRITE_BYTES}-byte write limit")
        if not path.parent.is_dir():
            raise NativeToolError("Parent directory must already exist")
        if path.exists() and not path.is_file():
            raise NativeToolError("Write target must be a regular file")
        fd, temporary = tempfile.mkstemp(prefix=".blind-sniper-write-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            if path.is_symlink():
                raise NativeToolError("Symlink write targets are forbidden")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {"path": normalized, "sha256": hashlib.sha256(raw).hexdigest(), "bytes_written": len(raw)}

    def _run_verification(self, arguments: dict[str, Any]) -> dict[str, Any]:
        command_id = arguments.get("command_id")
        command = COMMANDS.get(command_id)
        if command is None:
            raise NativeToolError("Verification command is not in the fixed allowlist")
        try:
            result = subprocess.run(
                command,
                cwd=self.workspace_root,
                env={"PATH": os.environ.get("PATH", ""), "PYTHONUNBUFFERED": "1"},
                capture_output=True,
                text=True,
                timeout=self.command_timeout,
                check=False,
            )
            stdout = redact(result.stdout or "")[-MAX_TOOL_OUTPUT_CHARS:]
            stderr = redact(result.stderr or "")[-MAX_TOOL_OUTPUT_CHARS:]
            return {
                "command_id": command_id,
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "exit_code": result.returncode,
                "stdout_excerpt": stdout,
                "stderr_excerpt": stderr,
            }
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return {
                "command_id": command_id,
                "status": "TIMED_OUT",
                "exit_code": None,
                "stdout_excerpt": redact(stdout)[-MAX_TOOL_OUTPUT_CHARS:],
                "stderr_excerpt": redact(stderr)[-MAX_TOOL_OUTPUT_CHARS:],
                "timeout_seconds": self.command_timeout,
            }

    def _run_browser(self, name: str, arguments: dict[str, Any], *, spec: Any, task: Any, run_id: str, tool_call_id: str) -> dict[str, Any]:
        if not os.environ.get("BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS", "").strip():
            raise NativeToolError("Native browser host must configure BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS")
        if task.lease_seconds <= 10:
            raise NativeToolError("Native browser action requires more than ten seconds of remaining lease budget")
        actions = {
            "browser.navigate": ("open", [arguments.get("url", "")]),
            "browser.snapshot": ("snapshot", []),
            "browser.get_url": ("get-url", []),
            "browser.tabs": ("tabs", []),
            "browser.screenshot": ("screenshot", [arguments.get("filename", "")]),
            "browser.click": ("click", [arguments.get("selector", "")]),
            "browser.fill": ("fill", [arguments.get("selector", ""), arguments.get("value", "")]),
            "browser.press": ("press", [arguments.get("key", "")]),
        }
        action, action_args = actions[name]
        session_id = "s" + hashlib.sha256(f"{task.task_id}:{run_id}".encode()).hexdigest()[:20]
        step_id = "tool-" + hashlib.sha256(f"{run_id}:{tool_call_id}".encode()).hexdigest()[:24]
        adapter = self.browser_adapter_factory(
            task_id=task.task_id,
            run_id=run_id,
            session_id=session_id,
            state_dir=self.browser_state_dir / task.task_id,
            timeout=min(45, task.lease_seconds - 10),
            approval_reference=spec.browser_approval_reference or None,
        )
        result = adapter.execute(action, step_id, *action_args)
        receipt = result.get("receipt", {})
        output = redact_text(str(result.get("output", "")))[:MAX_TOOL_OUTPUT_CHARS]
        error = redact(str(result.get("error", "")))[:2000]
        artifact_paths = receipt.get("artifact_paths", []) if isinstance(receipt, dict) else []
        return {
            "action": action,
            "status": "PASS" if receipt.get("exit_code") == 0 else "FAIL",
            "output_excerpt": output,
            "error": error,
            "artifact_paths": artifact_paths,
            "browser_receipt_digest": _digest(receipt),
        }

    def execute(
        self, *, name: str, arguments: dict[str, Any], spec: Any, task: Any,
        run_id: str, tool_call_id: str,
    ) -> dict[str, Any]:
        if name not in spec.tool_allowlist:
            raise NativeToolError(f"Tool {name!r} is not in this agent's allowlist")
        self.validate_spec(spec)
        if not isinstance(arguments, dict):
            raise NativeToolError("Tool arguments must be a JSON object")
        owner_id = str(getattr(task, "lease_owner_id", "")).strip()
        if not owner_id:
            raise NativeToolError("Tool execution requires the durable task lease owner")
        arguments_digest = _digest(arguments)
        self.queue.heartbeat(task_id=task.task_id, owner_id=owner_id, lease_seconds=task.lease_seconds)
        self.queue.reserve_tool_call(
            task_id=task.task_id, owner_id=owner_id, run_id=run_id,
            tool_call_id=tool_call_id, tool_name=name, arguments_digest=arguments_digest,
        )
        try:
            if name == "repo.read_file":
                result = self._read_file(arguments, spec)
                status = "PASS"
            elif name == "repo.write_file":
                result = self._write_file(arguments, spec)
                status = "PASS"
            elif name == "verification.run":
                result = self._run_verification(arguments)
                status = "PASS"
            elif name.startswith("browser."):
                result = self._run_browser(name, arguments, spec=spec, task=task, run_id=run_id, tool_call_id=tool_call_id)
                status = "PASS" if result.get("status") == "PASS" else "FAIL"
            else:
                raise NativeToolError(f"Tool {name!r} is not implemented")
        except Exception as exc:
            result = {"error": redact(f"{type(exc).__name__}: {exc}")}
            status = "FAIL"
        result_digest = _digest(result)
        self.queue.complete_tool_call(
            task_id=task.task_id, owner_id=owner_id, run_id=run_id,
            tool_call_id=tool_call_id, result_digest=result_digest, status=status,
        )
        self.queue.heartbeat(task_id=task.task_id, owner_id=owner_id, lease_seconds=task.lease_seconds)
        return {
            "ok": status == "PASS",
            "result": result,
            "receipt": {
                "task_id": task.task_id,
                "run_id": run_id,
                "tool_call_id": tool_call_id,
                "tool_name": name,
                "status": status,
                "result_digest": result_digest,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        }
