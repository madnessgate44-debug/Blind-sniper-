#!/usr/bin/env python3
"""Bounded adapter for the pinned agent-browser CLI.

The host supplies domain policy and any write approval through environment
variables. This module never invokes a shell and never persists page contents.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = "1.0.0"
ACTIONS = {"open", "snapshot", "click", "fill", "press", "screenshot", "get-url", "close", "tabs", "tab-new", "tab-switch", "tab-close", "frame", "upload", "download", "pdf", "clipboard-read", "clipboard-write", "clipboard-copy", "clipboard-paste"}
MUTATING_ACTIONS = {"click", "fill", "press", "upload", "clipboard-read", "clipboard-write", "clipboard-copy", "clipboard-paste"}
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
    return {item.strip().lower().removeprefix("*.").rstrip(".") for item in os.environ.get(name, "").split(",") if item.strip()}


def _matches(host: str, rule: str) -> bool:
    return host == rule or host.endswith("." + rule)


def redact_url_for_receipt(url: str | None) -> str | None:
    """Keep the origin for diagnostics while excluding path, query and fragment data."""
    if not url:
        return None
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host:
            return "[REDACTED_URL]"
        host = f"[{host}]" if ":" in host else host
        port = f":{parsed.port}" if parsed.port is not None else ""
        return f"{parsed.scheme}://{host}{port}/[REDACTED]"
    except ValueError:
        return "[REDACTED_URL]"


def _assert_public_host(host: str, port: int | None) -> None:
    literal = host.split("%", 1)[0]
    try:
        addresses = [ipaddress.ip_address(literal)]
    except ValueError:
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".lan", ".home", ".corp", ".test", ".invalid", ".example", ".onion")):
            raise BrowserPolicyError(f"Local or non-public host is not permitted: {host}")
        try:
            records = socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise BrowserPolicyError(f"DNS resolution failed for public host: {host}") from exc
        addresses = []
        for record in records:
            try:
                addresses.append(ipaddress.ip_address(record[4][0].split("%", 1)[0]))
            except ValueError:
                continue
    if not addresses:
        raise BrowserPolicyError(f"Host has no usable public IP address: {host}")
    for address in addresses:
        if address.version == 6 and address.ipv4_mapped:
            address = address.ipv4_mapped
        if not address.is_global:
            raise BrowserPolicyError(f"Host resolves to a non-public IP address: {address}")


def _disable_ipv6_egress(proc_root: Path = Path("/proc")) -> None:
    controls = list((proc_root / "sys/net/ipv6/conf").glob("*/disable_ipv6"))
    if not controls:
        raise BrowserPolicyError("Host cannot verify or disable IPv6 egress")
    try:
        for control in controls:
            if control.read_text(encoding="utf-8").strip() != "1":
                control.write_text("1", encoding="utf-8")
        if any(control.read_text(encoding="utf-8").strip() != "1" for control in controls):
            raise OSError("IPv6 disable control did not persist")
    except OSError as exc:
        raise BrowserPolicyError("Host must disable IPv6 egress before general browsing") from exc


def validate_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise BrowserPolicyError("Malformed URL or port") from exc
    general_https = os.environ.get("BLIND_SNIPER_BROWSER_GENERAL_HTTPS") == "1"
    scheme = parsed.scheme.lower()
    allowed_schemes = {"https"} if general_https else {"http", "https"}
    if scheme not in allowed_schemes or not parsed.hostname:
        if general_https:
            raise BrowserPolicyError("General browsing permits only absolute public HTTPS URLs")
        raise BrowserPolicyError("Only absolute HTTP(S) URLs are permitted")
    if parsed.username is not None or parsed.password is not None:
        raise BrowserPolicyError("URLs containing embedded credentials are not permitted")
    host = parsed.hostname.lower().rstrip(".")
    blocked = _domain_list("BLIND_SNIPER_BROWSER_BLOCKED_DOMAINS")
    if any(_matches(host, rule) for rule in blocked):
        raise BrowserPolicyError(f"Domain is blocked by host policy: {host}")
    if general_https:
        if os.environ.get("BLIND_SNIPER_BROWSER_REQUIRE_IPV6_DISABLE") != "1":
            raise BrowserPolicyError("General HTTPS requires a host-level IPv6 egress block")
        _disable_ipv6_egress()
        _assert_public_host(host, port)
        return host
    allowed = _domain_list("BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS")
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
        if str(state_dir) == ".blind-sniper/browser":
            state_dir = os.environ.get("BLIND_SNIPER_BROWSER_STATE_DIR", str(state_dir))
        self.state_dir = Path(state_dir).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state_dir, 0o700)
        self.sessions_dir = self.state_dir / "sessions"
        self.receipts_dir = self.state_dir / "receipts"
        self.artifacts_dir = self.state_dir / "artifacts"
        self.uploads_dir = self.state_dir / "uploads"
        self.profiles_dir = self.state_dir / "profiles"
        self.restore_urls_dir = self.state_dir / "resume"
        self.restore_url_file = self.restore_urls_dir / f"{session_id}.json"
        self.policy_file = self.state_dir / "action-policy.json"
        for directory in (self.sessions_dir, self.receipts_dir, self.artifacts_dir, self.uploads_dir, self.profiles_dir, self.restore_urls_dir):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(directory, 0o700)
        self.policy_file.write_text(json.dumps({
            "default": "deny",
            "allow": ["launch", "close", "navigate", "snapshot", "screenshot", "click", "fill", "upload", "download", "clipboard", "tab_list", "tab_new", "tab_switch", "tab_close", "frame", "frame_switch", "mainframe", "pdf", "scroll", "wait", "get", "url", "getattribute", "count", "interact", "read"],
        }, indent=2) + "\n", encoding="utf-8")
        self.session_file = self.sessions_dir / f"{session_id}.json"
        self.receipt_file = self.receipts_dir / f"{self.task_id}__{self.run_id}.jsonl"
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if not self.session_file.exists():
            state = {
                "schema_version": SCHEMA_VERSION, "task_id": self.task_id,
                "run_id": self.run_id, "session_id": self.session_id,
                "status": "NEW", "current_url": None, "created_at": utc_now(),
            }
            if self.restore_url_file.exists():
                state["restore_url"] = self._read_restore_url()
            return state
        try:
            state = json.loads(self.session_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BrowserAdapterError(f"Cannot recover session metadata: {exc}") from exc
        for key, expected in (("task_id", self.task_id), ("run_id", self.run_id), ("session_id", self.session_id)):
            if state.get(key) != expected:
                raise BrowserPolicyError(f"Session {key} mismatch; refusing cross-task reuse")
        if state.get("status") == "CLOSED":
            raise BrowserPolicyError("Session is closed; create a new session_id")
        if self.restore_url_file.exists():
            state["restore_url"] = self._read_restore_url()
        return state

    def _read_restore_url(self) -> str | None:
        try:
            value = json.loads(self.restore_url_file.read_text(encoding="utf-8")).get("url")
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            raise BrowserAdapterError(f"Cannot recover private browser resume URL: {exc}") from exc
        return value if isinstance(value, str) and value.startswith(("http://", "https://")) else None

    def _save_state(self) -> None:
        public_state = {key: value for key, value in self.state.items() if key != "restore_url"}
        temp = self.session_file.with_suffix(".tmp")
        temp.write_text(json.dumps(public_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, self.session_file)
        restore_url = self.state.get("restore_url")
        if isinstance(restore_url, str) and restore_url.startswith(("http://", "https://")):
            resume_temp = self.restore_url_file.with_suffix(".tmp")
            resume_temp.write_text(json.dumps({"url": restore_url}) + "\n", encoding="utf-8")
            os.chmod(resume_temp, 0o600)
            os.replace(resume_temp, self.restore_url_file)

    def _clear_stale_profile_lock(self, profile_dir: Path) -> None:
        lock = profile_dir / "SingletonLock"
        if not lock.is_symlink():
            return
        try:
            target = os.readlink(lock)
        except OSError:
            return
        pid = target.rsplit("-", 1)[-1]
        if not pid.isdigit() or (Path("/proc") / pid).exists():
            return
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            candidate = profile_dir / name
            if candidate.is_symlink():
                candidate.unlink(missing_ok=True)

    def _command(self, *args: str) -> tuple[int, str, str, list[str]]:
        allowed_domains = ",".join(
            item.strip() for item in os.environ.get("BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS", "").split(",")
            if item.strip()
        )
        general_https = os.environ.get("BLIND_SNIPER_BROWSER_GENERAL_HTTPS") == "1"
        if not allowed_domains and not general_https:
            raise BrowserPolicyError("The host must provide BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS or enable general HTTPS policy")
        idle_timeout = os.environ.get("BLIND_SNIPER_BROWSER_IDLE_TIMEOUT", "1h").strip()
        if not re.fullmatch(r"(?:0|[1-9][0-9]*(?:ms|s|m|h))", idle_timeout):
            raise BrowserPolicyError("BLIND_SNIPER_BROWSER_IDLE_TIMEOUT must be 0 or a positive duration such as 30m or 1h")
        persistent_profile = os.environ.get("BLIND_SNIPER_BROWSER_PERSISTENT_PROFILE") == "1"
        command = [self.binary, "--session", self.session_id, "--idle-timeout", idle_timeout]
        if persistent_profile:
            profile_dir = self.profiles_dir / self.session_id
            profile_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(profile_dir, 0o700)
            self._clear_stale_profile_lock(profile_dir)
            command.extend(["--profile", str(profile_dir)])
        elif not general_https:
            command.extend(["--allowed-domains", allowed_domains])
        command.extend([
            "--action-policy", str(self.policy_file),
            "--content-boundaries", "--max-output", "50000", "--json",
            *args,
        ])
        executable_path = os.environ.get("AGENT_BROWSER_EXECUTABLE_PATH", "").strip()
        if executable_path:
            command[1:1] = ["--executable-path", executable_path]
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
            return None
        try:
            data = json.loads(stdout)
            pending = [data]
            while pending:
                item = pending.pop()
                if isinstance(item, dict):
                    for key, value in item.items():
                        if key.lower() in {"url", "value"} and isinstance(value, str) and (value.startswith(("http://", "https://")) or value == "about:blank"):
                            return value
                        pending.append(value)
                elif isinstance(item, list):
                    pending.extend(item)
        except json.JSONDecodeError:
            pass
        match = re.search(r"https?://[^\s\"']+", stdout)
        return match.group(0) if match else None

    def _cli_data_field(self, *args: str, field: str) -> Any:
        code, stdout, _, _ = self._command("get", *args)
        if code != 0:
            return None
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            return None
        pending = [parsed]
        while pending:
            item = pending.pop(0)
            if isinstance(item, dict):
                for key, value in item.items():
                    if key.lower() == field.lower():
                        return value
                    pending.append(value)
            elif isinstance(item, list):
                pending.extend(item)
        return None

    def _assert_fill_target_safe(self, selector: str) -> None:
        sensitive = re.compile(
            r"password|passwd|secret|token|api[_-]?key|otp|one.?time.?code|"
            r"authenticator|credential|passcode|security.?code|cvv|cvc|"
            r"cc-(?:number|exp|csc)|credit.?card|ssn|social.?security",
            re.I,
        )
        if sensitive.search(selector):
            raise BrowserPolicyError("Sensitive credential or payment fields cannot be filled by automation")
        credential_fields = self._cli_data_field(
            "count",
            'input[type="password"],input[autocomplete*="password"],input[autocomplete="one-time-code"]',
            field="count",
        )
        if credential_fields is None:
            raise BrowserPolicyError("Cannot verify whether this page contains credential fields; refusing form fill")
        try:
            if int(credential_fields) > 0:
                raise BrowserPolicyError("Page contains password or one-time-code fields; user authentication must be handled manually")
        except (TypeError, ValueError) as exc:
            raise BrowserPolicyError("Cannot verify page credential fields; refusing form fill") from exc
        attributes: dict[str, str] = {}
        for name in ("type", "autocomplete", "name", "id", "placeholder", "aria-label"):
            value = self._cli_data_field("attr", selector, name, field="value")
            if isinstance(value, (str, int, float)) and str(value).strip():
                attributes[name] = str(value).strip()
        if not attributes and not re.search(r"textarea|contenteditable", selector, re.I):
            raise BrowserPolicyError("Cannot verify the target field; refusing form fill")
        if sensitive.search(" ".join(attributes.values())):
            raise BrowserPolicyError("Sensitive credential or payment fields cannot be filled by automation")
        if attributes.get("type", "").lower() in {"password", "hidden"}:
            raise BrowserPolicyError("Password and hidden fields cannot be filled by automation")
        if attributes.get("autocomplete", "").lower() in {
            "current-password", "new-password", "one-time-code",
            "cc-number", "cc-exp", "cc-csc",
        }:
            raise BrowserPolicyError("Credential, MFA and payment fields cannot be filled by automation")

    def _ensure_page_restored(self) -> None:
        restore_url = self.state.get("restore_url")
        if not isinstance(restore_url, str) or not restore_url:
            return
        current_url = self._current_url()
        if current_url and current_url != "about:blank":
            validate_url(current_url)
            self.state["restore_url"] = current_url
            self.state["current_url"] = redact_url_for_receipt(current_url)
            return
        validate_url(restore_url)
        code, _, stderr, _ = self._command("open", restore_url)
        if code != 0:
            raise BrowserAdapterError(f"Cannot restore the last browser page: {stderr or 'browser open failed'}")
        current_url = self._current_url()
        if not current_url or current_url == "about:blank":
            raise BrowserAdapterError("Browser page restoration did not return an HTTP(S) URL")
        validate_url(current_url)
        self.state["restore_url"] = current_url
        self.state["current_url"] = redact_url_for_receipt(current_url)

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

    def _contained_file(self, root: Path, supplied: str, *, must_exist: bool, max_bytes: int = 10 * 1024 * 1024) -> Path:
        candidate = Path(supplied)
        if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
            raise BrowserPolicyError("File paths must be relative and cannot traverse directories")
        root_resolved = root.resolve()
        target = (root_resolved / candidate).resolve()
        if target != root_resolved and root_resolved not in target.parents:
            raise BrowserPolicyError("File path escapes its permitted workspace")
        if must_exist:
            if not target.is_file():
                raise BrowserPolicyError("Upload source must be an existing regular file in the upload workspace")
            if target.stat().st_size > max_bytes:
                raise BrowserPolicyError(f"File exceeds the {max_bytes}-byte limit")
        else:
            if target.exists():
                raise BrowserPolicyError("Output file already exists; choose a new filename")
            target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def execute(self, action: str, step_id: str, *args: str) -> dict[str, Any]:
        if action not in ACTIONS:
            raise BrowserPolicyError(f"Unsupported browser action: {action}")
        _safe_id(step_id, "step_id")
        self._ensure_step_unused(step_id)
        started = utc_now()
        requested_url = None
        artifact_paths: list[str] = []

        if action not in {"open", "close"}:
            self._ensure_page_restored()

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
            self._assert_fill_target_safe(args[0])
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
            target = self._contained_file(self.artifacts_dir, args[0], must_exist=False)
            cli_args = ["screenshot", str(target)]
            artifact_paths.append(str(target))
        elif action == "tabs":
            if args:
                raise BrowserPolicyError("tabs takes no arguments")
            cli_args = ["tab"]
        elif action == "tab-new":
            if len(args) != 1:
                raise BrowserPolicyError("tab-new requires exactly one allowlisted URL")
            validate_url(args[0])
            requested_url = args[0]
            self.state["current_url"] = args[0]
            cli_args = ["tab", "new", args[0]]
        elif action == "tab-switch":
            if len(args) != 1 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}|t[1-9][0-9]*", args[0]):
                raise BrowserPolicyError("tab-switch requires a valid tab id or label")
            cli_args = ["tab", args[0]]
        elif action == "tab-close":
            if len(args) != 1 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}|t[1-9][0-9]*", args[0]):
                raise BrowserPolicyError("tab-close requires a valid tab id or label")
            cli_args = ["tab", "close", args[0]]
        elif action == "frame":
            if len(args) != 1 or not args[0] or len(args[0]) > 256:
                raise BrowserPolicyError("frame requires one bounded selector, element ref, name or URL")
            if args[0].lower() != "main" and not args[0].startswith("@") and re.match(r"^[a-z]+:", args[0], re.I):
                validate_url(args[0])
            cli_args = ["frame", args[0]]
        elif action == "upload":
            self._assert_write_approved()
            if len(args) != 2 or not args[0] or len(args[0]) > 256:
                raise BrowserPolicyError("upload requires a selector and a workspace-relative filename")
            validate_url(self.state.get("current_url") or "")
            source = self._contained_file(self.state_dir / "uploads", args[1], must_exist=True)
            if source.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv", ".docx", ".xlsx"}:
                raise BrowserPolicyError("Upload file type is not permitted")
            cli_args = ["upload", args[0], str(source)]
        elif action == "download":
            validate_url(self.state.get("current_url") or "")
            if len(args) != 2 or not args[0] or len(args[0]) > 256 or Path(args[1]).name != args[1]:
                raise BrowserPolicyError("download requires a selector and a simple output filename")
            target = self._contained_file(self.artifacts_dir, args[1], must_exist=False, max_bytes=25 * 1024 * 1024)
            cli_args = ["download", args[0], str(target)]
            artifact_paths.append(str(target))
        elif action == "pdf":
            validate_url(self.state.get("current_url") or "")
            if len(args) != 1 or Path(args[0]).name != args[0] or not args[0].lower().endswith(".pdf"):
                raise BrowserPolicyError("pdf requires a simple .pdf filename")
            target = self._contained_file(self.artifacts_dir, args[0], must_exist=False, max_bytes=25 * 1024 * 1024)
            cli_args = ["pdf", str(target)]
            artifact_paths.append(str(target))
        elif action == "clipboard-read":
            if args:
                raise BrowserPolicyError("clipboard-read takes no arguments")
            validate_url(self.state.get("current_url") or "")
            cli_args = ["clipboard", "read"]
        elif action == "clipboard-write":
            self._assert_write_approved()
            if len(args) != 1 or len(args[0]) > 10000:
                raise BrowserPolicyError("clipboard-write requires one text value of at most 10000 characters")
            validate_url(self.state.get("current_url") or "")
            cli_args = ["clipboard", "write", args[0]]
        elif action == "clipboard-copy":
            self._assert_write_approved()
            if args:
                raise BrowserPolicyError("clipboard-copy takes no arguments")
            validate_url(self.state.get("current_url") or "")
            cli_args = ["clipboard", "copy"]
        elif action == "clipboard-paste":
            self._assert_write_approved()
            if args:
                raise BrowserPolicyError("clipboard-paste takes no arguments")
            validate_url(self.state.get("current_url") or "")
            cli_args = ["clipboard", "paste"]
        elif action == "get-url":
            cli_args = ["get", "url"]
        else:
            cli_args = ["close"]

        if action not in {"open", "get-url", "close", "tabs", "tab-new", "tab-switch", "tab-close", "frame"}:
            requested_url = self.state.get("current_url")
        code, stdout, stderr, command = self._command(*cli_args)
        if action == "download" and code == 0:
            downloaded = Path(artifact_paths[0])
            if not downloaded.is_file():
                code = 2
                stderr = (stderr + "\nDownload command completed without the expected file").strip()
            elif downloaded.stat().st_size > 25 * 1024 * 1024:
                downloaded.unlink(missing_ok=True)
                code = 2
                stderr = (stderr + "\nDownloaded file exceeded the 25 MiB limit and was removed").strip()
        observed_url = requested_url
        policy_error = None
        if action in {"open", "tab-new"}:
            self.state["status"] = "OPEN"
        if action == "open" or action in MUTATING_ACTIONS or action == "get-url" or action in {"tab-new", "tab-switch", "tab-close"}:
            observed_url = self._current_url()
            if observed_url:
                try:
                    validate_url(observed_url)
                    self.state["restore_url"] = observed_url
                    self.state["current_url"] = redact_url_for_receipt(observed_url)
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
            "requested_url": redact_url_for_receipt(requested_url),
            "observed_url": redact_url_for_receipt(observed_url),
            "started_at": started, "completed_at": utc_now(),
            "command": [
                "[REDACTED]" if action in {"fill", "clipboard-write"} and i == len(command) - 1
                else "[WORKSPACE_FILE]" if action == "upload" and i == len(command) - 1
                else redact_url_for_receipt(value) if value.startswith(("http://", "https://"))
                else value
                for i, value in enumerate(command)
            ],
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


def main(argv: list[str] | None = None) -> int:
    """Prevent bypassing the native task/lease dispatcher via the adapter CLI."""
    print(
        "BLOCKED: invoke browser actions through scripts/blind_sniper_browser_dispatch.py",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
