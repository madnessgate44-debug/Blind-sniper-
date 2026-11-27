"""Connector status and authorization registry.

No connector is operational until an authenticated integration test passes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from collections.abc import Mapping
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import queue
import threading
from typing import Any, Callable
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


SCHEMA_VERSION = 1
DEFAULT_MAX_AGE_SECONDS = 3600
REFRESH_SKEW_SECONDS = 120

AUTH_KINDS = ("workflow_token", "oauth2_refresh", "api_key", "local_none")
AUTH_STATUSES = ("unconfigured", "configured_unverified", "verified", "expired", "error")
REFRESH_STATES = ("not_applicable", "fresh", "refreshed", "failed")
DESTRUCTIVE_PREFIXES = ("delete_", "send_", "comment_")
DESTRUCTIVE_EXACT = {"open_pull_request"}

HttpCallable = Callable[[str, str, dict[str, str] | None, bytes | None], tuple[int, dict[str, str], bytes]]
VerifierCallable = Callable[[dict[str, str], HttpCallable], tuple[bool, list[str], float | None, str | None]]


def _utc_now_iso(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(time.time() if ts is None else ts, tz=timezone.utc)
    return dt.isoformat()


def _parse_iso_to_epoch(value: str | None) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def default_http(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    req_headers = dict(headers or {})
    req = urllib_request.Request(url=url, data=data, headers=req_headers, method=method.upper())
    try:
        with urllib_request.urlopen(req, timeout=10) as resp:
            resp_headers = {k: v for k, v in resp.headers.items()}
            body = resp.read()
            return int(resp.status), resp_headers, body
    except urllib_error.HTTPError as exc:
        resp_headers = {k: v for k, v in exc.headers.items()} if exc.headers else {}
        body = exc.read() if exc.fp else b""
        return int(exc.code), resp_headers, body
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def redact(text: str, extra_secrets: list[str] | None = None) -> str:
    if not text:
        return ""
    out = text
    for secret in extra_secrets or []:
        if secret and len(secret) >= 3:
            out = out.replace(secret, "[REDACTED]")
    out = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", out)
    out = re.sub(r"(?i)((?:token|secret|api_key|apikey|password|authorization|key)[=:\s]+)[A-Za-z0-9._~+/=-]{6,}", r"\1[REDACTED]", out)
    out = re.sub(r"([?&](?:access_token|refresh_token|client_secret|key|token)=)[^&\s]+", r"\1[REDACTED]", out)
    return out


def _collect_env_secrets(env: dict[str, str], spec: ConnectorSpec | None = None) -> list[str]:
    secret_keys = {
        "GITHUB_TOKEN",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REFRESH_TOKEN",
        "WHATSAPP_ACCESS_TOKEN",
        "GEMINI_API_KEY",
    }
    if spec is not None:
        secret_keys.update(spec.env_vars)
        if spec.token_env_var:
            secret_keys.add(spec.token_env_var)
        if spec.expires_env_var:
            secret_keys.add(spec.expires_env_var)
    values: list[str] = []
    for k in secret_keys:
        val = env.get(k)
        if val:
            values.append(val)
    return values


@dataclass
class ConnectorSpec:
    connector_id: str
    display_name: str
    auth_kind: str
    env_vars: list[str] = field(default_factory=list)
    scopes_required: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)
    token_env_var: str | None = None
    expires_env_var: str | None = None
    operation_scopes: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ConnectorStatus:
    connector_id: str
    auth_status: str = "unconfigured"
    granted_scopes: list[str] = field(default_factory=list)
    operations_available: list[str] = field(default_factory=list)
    health: str = "unknown"
    last_verified_at: str | None = None
    last_error: str | None = None
    token_expires_at: float | None = None
    refresh_state: str = "not_applicable"
    checked_by: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConnectorStatus:
        return cls(
            connector_id=str(data["connector_id"]),
            auth_status=str(data.get("auth_status", "unconfigured")),
            granted_scopes=list(data.get("granted_scopes") or []),
            operations_available=list(data.get("operations_available") or []),
            health=str(data.get("health", "unknown")),
            last_verified_at=data.get("last_verified_at"),
            last_error=data.get("last_error"),
            token_expires_at=data.get("token_expires_at"),
            refresh_state=str(data.get("refresh_state", "not_applicable")),
            checked_by=str(data.get("checked_by", "none")),
        )


class Connector(ABC):
    """Callable connector contract. Tool definitions use JSON Schema objects.

    Cancellation contract: a connector must set ``cancellable = True`` and accept a ``cancel``
    threading.Event keyword in call(); it must stop all work and side effects promptly once the
    event is set. Tools must declare "side_effects": "read_only" to be retry-safe after a timeout;
    anything else is treated as mutating and a stopped timeout stays an unresolved partial outcome.
    A thread cannot be killed, so a connector that does not declare this is refused
    (fail closed) rather than run with a timeout that cannot stop it.
    """

    cancellable: bool = False

    @property
    @abstractmethod
    def connector_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def tools(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def call(self, tool_name: str, arguments: dict[str, Any], *, timeout_s: float,
             cancel: threading.Event | None = None) -> dict[str, Any]:
        raise NotImplementedError


def _google_spec(
    connector_id: str,
    display_name: str,
    readonly_scope: str,
    write_scope: str,
    read_ops: list[str],
    write_ops: list[str],
) -> ConnectorSpec:
    op_scopes: dict[str, list[str]] = {}
    for op in read_ops:
        op_scopes[op] = [readonly_scope]
    for op in write_ops:
        op_scopes[op] = [write_scope]
    return ConnectorSpec(
        connector_id=connector_id,
        display_name=display_name,
        auth_kind="oauth2_refresh",
        env_vars=["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"],
        scopes_required=[readonly_scope],
        operations=read_ops + write_ops,
        token_env_var="GOOGLE_REFRESH_TOKEN",
        expires_env_var=None,
        operation_scopes=op_scopes,
    )


BUILTIN_SPECS: dict[str, ConnectorSpec] = {
    "github": ConnectorSpec(
        connector_id="github",
        display_name="GitHub",
        auth_kind="workflow_token",
        env_vars=["GITHUB_TOKEN"],
        scopes_required=[],
        operations=["read_repo", "list_issues", "comment_issue", "open_pull_request", "read_actions"],
        token_env_var="GITHUB_TOKEN",
        expires_env_var=None,
        operation_scopes={
            "read_repo": [],
            "list_issues": [],
            "comment_issue": [],
            "open_pull_request": [],
            "read_actions": [],
        },
    ),
    "google_drive": _google_spec(
        connector_id="google_drive",
        display_name="Google Drive",
        readonly_scope="https://www.googleapis.com/auth/drive.readonly",
        write_scope="https://www.googleapis.com/auth/drive.file",
        read_ops=["list_files", "read_file_metadata", "download_file"],
        write_ops=["create_file", "update_file", "delete_file"],
    ),
    "gmail": _google_spec(
        connector_id="gmail",
        display_name="Gmail",
        readonly_scope="https://www.googleapis.com/auth/gmail.readonly",
        write_scope="https://www.googleapis.com/auth/gmail.send",
        read_ops=["list_messages", "read_message"],
        write_ops=["send_message", "delete_message"],
    ),
    "google_calendar": _google_spec(
        connector_id="google_calendar",
        display_name="Google Calendar",
        readonly_scope="https://www.googleapis.com/auth/calendar.readonly",
        write_scope="https://www.googleapis.com/auth/calendar.events",
        read_ops=["list_events", "get_event"],
        write_ops=["create_event", "update_event", "delete_event"],
    ),
    "google_docs": _google_spec(
        connector_id="google_docs",
        display_name="Google Docs",
        readonly_scope="https://www.googleapis.com/auth/documents.readonly",
        write_scope="https://www.googleapis.com/auth/documents",
        read_ops=["read_document"],
        write_ops=["update_document", "create_document"],
    ),
    "google_sheets": _google_spec(
        connector_id="google_sheets",
        display_name="Google Sheets",
        readonly_scope="https://www.googleapis.com/auth/spreadsheets.readonly",
        write_scope="https://www.googleapis.com/auth/spreadsheets",
        read_ops=["read_values", "get_spreadsheet"],
        write_ops=["write_values", "append_values", "create_spreadsheet"],
    ),
    "whatsapp_business": ConnectorSpec(
        connector_id="whatsapp_business",
        display_name="WhatsApp Business",
        auth_kind="api_key",
        env_vars=["WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"],
        scopes_required=[],
        operations=["send_message", "read_profile"],
        token_env_var="WHATSAPP_ACCESS_TOKEN",
        expires_env_var=None,
        operation_scopes={
            "send_message": [],
            "read_profile": [],
        },
    ),
    "model_gemini": ConnectorSpec(
        connector_id="model_gemini",
        display_name="Gemini Model",
        auth_kind="api_key",
        env_vars=["GEMINI_API_KEY"],
        scopes_required=[],
        operations=["generate", "list_models"],
        token_env_var="GEMINI_API_KEY",
        expires_env_var=None,
        operation_scopes={
            "generate": [],
            "list_models": [],
        },
    ),
    "browser": ConnectorSpec(
        connector_id="browser",
        display_name="Browser",
        auth_kind="local_none",
        env_vars=[],
        scopes_required=[],
        operations=["open_url", "screenshot", "extract_text"],
        token_env_var=None,
        expires_env_var=None,
    ),
    "files": ConnectorSpec(
        connector_id="files",
        display_name="Local Files",
        auth_kind="local_none",
        env_vars=[],
        scopes_required=[],
        operations=["read_file", "write_file", "list_dir"],
        token_env_var=None,
        expires_env_var=None,
    ),
    "terminal": ConnectorSpec(
        connector_id="terminal",
        display_name="Terminal",
        auth_kind="local_none",
        env_vars=[],
        scopes_required=[],
        operations=["run_command"],
        token_env_var=None,
        expires_env_var=None,
    ),
}


def verify_github(env: dict[str, str], http: HttpCallable) -> tuple[bool, list[str], float | None, str | None]:
    secrets = _collect_env_secrets(env, BUILTIN_SPECS["github"])
    token = (env.get("GITHUB_TOKEN") or "").strip()
    if not token:
        return False, [], None, "Missing GITHUB_TOKEN"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "blind-sniper-connector-registry",
    }
    status1, hdrs1, body1 = http("GET", "https://api.github.com/rate_limit", headers, None)
    if status1 < 200 or status1 >= 300:
        msg = redact(f"GitHub rate_limit check failed with status {status1}: {body1.decode('utf-8', errors='replace')[:200]}", secrets)
        return False, [], None, msg

    granted: list[str] = []
    scope_hdr = ""
    for k, v in (hdrs1 or {}).items():
        if k.lower() == "x-oauth-scopes":
            scope_hdr = v
            break
    if scope_hdr.strip():
        granted = [s.strip() for s in scope_hdr.split(",") if s.strip()]

    repo = (env.get("GITHUB_REPOSITORY") or "").strip()
    if repo and "/" in repo:
        status2, hdrs2, body2 = http("GET", f"https://api.github.com/repos/{repo}", headers, None)
        if status2 < 200 or status2 >= 300:
            msg = redact(f"GitHub repo check failed ({repo}) with status {status2}: {body2.decode('utf-8', errors='replace')[:200]}", secrets)
            return False, granted, None, msg
        for k, v in (hdrs2 or {}).items():
            if k.lower() == "x-oauth-scopes" and v.strip():
                granted = [s.strip() for s in v.split(",") if s.strip()]
                break

    return True, granted, None, None


def verify_model_gemini(env: dict[str, str], http: HttpCallable) -> tuple[bool, list[str], float | None, str | None]:
    secrets = _collect_env_secrets(env, BUILTIN_SPECS["model_gemini"])
    api_key = (env.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return False, [], None, "Missing GEMINI_API_KEY"
    headers = {
        "x-goog-api-key": api_key,
        "Accept": "application/json",
    }
    status, _, body = http("GET", "https://generativelanguage.googleapis.com/v1beta/models", headers, None)
    if status < 200 or status >= 300:
        msg = redact(f"Gemini models check failed with status {status}: {body.decode('utf-8', errors='replace')[:200]}", secrets)
        return False, [], None, msg
    return True, [], None, None


def verify_whatsapp_business(env: dict[str, str], http: HttpCallable) -> tuple[bool, list[str], float | None, str | None]:
    secrets = _collect_env_secrets(env, BUILTIN_SPECS["whatsapp_business"])
    token = (env.get("WHATSAPP_ACCESS_TOKEN") or "").strip()
    phone_id = (env.get("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    if not token or not phone_id:
        return False, [], None, "Missing WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    url = f"https://graph.facebook.com/v20.0/{urllib_parse.quote(phone_id, safe='')}"
    status, _, body = http("GET", url, headers, None)
    if status < 200 or status >= 300:
        msg = redact(f"WhatsApp Business check failed with status {status}: {body.decode('utf-8', errors='replace')[:200]}", secrets)
        return False, [], None, msg
    return True, [], None, None


def make_google_verifier(
    spec: ConnectorSpec,
    in_memory_tokens: dict[str, tuple[str, float | None]] | None = None,
) -> VerifierCallable:
    def _verify(env: dict[str, str], http: HttpCallable) -> tuple[bool, list[str], float | None, str | None]:
        secrets = _collect_env_secrets(env, spec)
        client_id = (env.get("GOOGLE_CLIENT_ID") or "").strip()
        client_secret = (env.get("GOOGLE_CLIENT_SECRET") or "").strip()
        refresh_token = (env.get("GOOGLE_REFRESH_TOKEN") or "").strip()
        if not client_id or not client_secret or not refresh_token:
            return False, [], None, "Missing GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, or GOOGLE_REFRESH_TOKEN"

        form_data = urllib_parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")
        token_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        status1, _, body1 = http("POST", "https://oauth2.googleapis.com/token", token_headers, form_data)
        if status1 < 200 or status1 >= 300:
            msg = redact(f"Google token refresh failed with status {status1}: {body1.decode('utf-8', errors='replace')[:200]}", secrets)
            return False, [], None, msg

        try:
            payload1 = json.loads(body1.decode("utf-8"))
        except Exception as exc:
            return False, [], None, redact(f"Invalid Google token response JSON: {exc}", secrets)

        access_token = str(payload1.get("access_token") or "").strip()
        if not access_token:
            return False, [], None, "Google token response missing access_token"

        expires_in_raw = payload1.get("expires_in")
        expires_in_seconds: float | None = None
        if expires_in_raw is not None:
            try:
                expires_in_seconds = float(expires_in_raw)
            except (TypeError, ValueError):
                expires_in_seconds = None

        info_url = "https://www.googleapis.com/oauth2/v3/tokeninfo?access_token=" + urllib_parse.quote(access_token, safe="")
        status2, _, body2 = http("GET", info_url, {"Accept": "application/json"}, None)
        if status2 < 200 or status2 >= 300:
            msg = redact(f"Google tokeninfo failed with status {status2}: {body2.decode('utf-8', errors='replace')[:200]}", secrets)
            return False, [], expires_in_seconds, msg

        try:
            payload2 = json.loads(body2.decode("utf-8"))
        except Exception as exc:
            return False, [], expires_in_seconds, redact(f"Invalid Google tokeninfo JSON: {exc}", secrets)

        if "expires_in" in payload2:
            try:
                expires_in_seconds = float(payload2["expires_in"])
            except (TypeError, ValueError):
                pass

        raw_scope = str(payload2.get("scope") or "").strip()
        granted_scopes = [s.strip() for s in raw_scope.split() if s.strip()]

        if in_memory_tokens is not None:
            mem_expires_at = (time.time() + expires_in_seconds) if expires_in_seconds is not None else None
            in_memory_tokens[spec.connector_id] = (access_token, mem_expires_at)

        missing = [sc for sc in spec.scopes_required if sc not in granted_scopes]
        if missing:
            return False, granted_scopes, expires_in_seconds, f"Missing required scopes: {', '.join(missing)}"

        return True, granted_scopes, expires_in_seconds, None

    return _verify

def verify_browser(env: dict[str, str], http: HttpCallable) -> tuple[bool, list[str], float | None, str | None]:
    found = shutil.which("google-chrome") or shutil.which("chromium")
    if not found:
        return False, [], None, "Neither google-chrome nor chromium found in PATH"
    return True, [], None, None


def verify_files(env: dict[str, str], http: HttpCallable) -> tuple[bool, list[str], float | None, str | None]:
    try:
        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", delete=True) as tmp:
            tmp.write("blind-sniper-probe")
            tmp.flush()
            tmp.seek(0)
            content = tmp.read()
        if content != "blind-sniper-probe":
            return False, [], None, "Temp file read-back mismatch"
        return True, [], None, None
    except Exception as exc:
        return False, [], None, redact(f"Local files probe failed: {exc}", _collect_env_secrets(env))


def verify_terminal(env: dict[str, str], http: HttpCallable) -> tuple[bool, list[str], float | None, str | None]:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", "pass"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            return False, [], None, redact(f"Python probe exited with {proc.returncode}", _collect_env_secrets(env))
        return True, [], None, None
    except Exception as exc:
        return False, [], None, redact(f"Terminal probe failed: {exc}", _collect_env_secrets(env))


def build_verifiers(in_memory_tokens: dict[str, tuple[str, float | None]] | None = None) -> dict[str, VerifierCallable]:
    verifiers: dict[str, VerifierCallable] = {
        "github": verify_github,
        "model_gemini": verify_model_gemini,
        "whatsapp_business": verify_whatsapp_business,
        "browser": verify_browser,
        "files": verify_files,
        "terminal": verify_terminal,
    }
    for cid, spec in BUILTIN_SPECS.items():
        if spec.auth_kind == "oauth2_refresh":
            verifiers[cid] = make_google_verifier(spec, in_memory_tokens=in_memory_tokens)
    return verifiers


ROLES: dict[str, list[tuple[str, str]]] = {
    "planner": [
        ("github", "read_*"),
        ("github", "list_*"),
        ("google_drive", "list_*"),
        ("google_drive", "read_*"),
        ("google_calendar", "list_*"),
        ("google_calendar", "get_*"),
        ("google_docs", "read_*"),
        ("google_sheets", "read_*"),
        ("google_sheets", "get_*"),
        ("model_gemini", "list_models"),
        ("files", "read_*"),
        ("files", "list_*"),
    ],
    "researcher": [
        ("github", "read_*"),
        ("github", "list_*"),
        ("google_drive", "list_*"),
        ("google_drive", "read_*"),
        ("google_drive", "download_*"),
        ("gmail", "list_*"),
        ("gmail", "read_*"),
        ("google_docs", "read_*"),
        ("google_sheets", "read_*"),
        ("google_sheets", "get_*"),
        ("model_gemini", "generate"),
        ("model_gemini", "list_models"),
        ("browser", "*"),
        ("files", "read_*"),
        ("files", "list_*"),
    ],
    "engineer": [
        ("github", "*"),
        ("google_docs", "*"),
        ("google_sheets", "*"),
        ("model_gemini", "generate"),
        ("model_gemini", "list_models"),
        ("browser", "*"),
        ("files", "*"),
        ("terminal", "*"),
    ],
    "qa_verifier": [
        ("github", "read_*"),
        ("github", "list_*"),
        ("browser", "*"),
        ("files", "read_*"),
        ("files", "list_*"),
        ("terminal", "*"),
    ],
    "release_manager": [
        ("github", "read_*"),
        ("github", "list_*"),
        ("github", "open_pull_request"),
        ("google_docs", "read_*"),
        ("google_sheets", "read_*"),
        ("google_sheets", "get_*"),
        ("files", "read_*"),
        ("files", "list_*"),
    ],
    "watcher": [
        ("github", "read_*"),
        ("github", "list_*"),
        ("gmail", "list_*"),
        ("gmail", "read_*"),
        ("google_calendar", "list_*"),
        ("google_calendar", "get_*"),
        ("whatsapp_business", "read_*"),
        ("files", "read_*"),
        ("files", "list_*"),
    ],
    "worker_executor": [
        ("github", "*"),
        ("google_drive", "*"),
        ("gmail", "*"),
        ("google_calendar", "*"),
        ("google_docs", "*"),
        ("google_sheets", "*"),
        ("whatsapp_business", "*"),
        ("model_gemini", "*"),
        ("browser", "*"),
        ("files", "*"),
        ("terminal", "*"),
    ],
}


def is_destructive_operation(operation: str) -> bool:
    if operation in DESTRUCTIVE_EXACT:
        return True
    return any(operation.startswith(prefix) for prefix in DESTRUCTIVE_PREFIXES)


def _is_configured(spec: ConnectorSpec, env: dict[str, str]) -> bool:
    if spec.auth_kind == "local_none":
        return True
    if not spec.env_vars:
        return False
    return all(bool((env.get(var) or "").strip()) for var in spec.env_vars)


def _receipt_age_seconds(st: ConnectorStatus, now: float) -> float | None:
    verified_ts = _parse_iso_to_epoch(st.last_verified_at)
    if verified_ts is None:
        return None
    return max(0.0, now - verified_ts)


def _effective_status(
    spec: ConnectorSpec,
    raw_status: ConnectorStatus,
    env: dict[str, str],
    now: float,
    max_age_seconds: float,
) -> ConnectorStatus:
    st = ConnectorStatus.from_dict(raw_status.to_dict())
    if not _is_configured(spec, env):
        st.auth_status = "unconfigured"
        st.operations_available = []
        if st.health == "unknown":
            st.health = "unconfigured"
        return st

    if spec.auth_kind == "oauth2_refresh":
        if st.token_expires_at is not None and st.token_expires_at <= now:
            st.auth_status = "expired"
            st.operations_available = []
            st.health = "degraded"
            return st
        if st.token_expires_at is not None and (st.token_expires_at - now) <= REFRESH_SKEW_SECONDS:
            if st.auth_status == "verified":
                st.auth_status = "configured_unverified"
            st.operations_available = []
            return st

    if st.auth_status == "verified":
        age = _receipt_age_seconds(st, now)
        if age is None or age >= max_age_seconds:
            st.auth_status = "configured_unverified"
            st.operations_available = []
        else:
            st.operations_available = list(spec.operations)
    else:
        st.operations_available = []

    return st


class ConnectorRegistry:
    def __init__(
        self,
        specs: dict[str, ConnectorSpec] | None = None,
        env: dict[str, str] | None = None,
        http: HttpCallable | None = None,
        verifiers: dict[str, VerifierCallable] | None = None,
        max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
        connectors: list[Connector] | None = None,
        call_receipts_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self.specs: dict[str, ConnectorSpec] = dict(specs if specs is not None else BUILTIN_SPECS)
        self.env: dict[str, str] = dict(env if env is not None else os.environ)
        self.http: HttpCallable = http if http is not None else default_http
        self._in_memory_tokens: dict[str, tuple[str, float | None]] = {}
        self.verifiers: dict[str, VerifierCallable] = (
            dict(verifiers) if verifiers is not None else build_verifiers(self._in_memory_tokens)
        )
        self.max_age_seconds: float = float(max_age_seconds)
        self._connectors = {c.connector_id: c for c in (connectors or [])}
        self.call_receipts: list[dict[str, Any]] = []
        self.cancel_grace_s: float = 1.0
        self._unknown: dict[str, dict[str, Any]] = {}  # call digest -> unresolved execution state
        self._unknown_lock = threading.Lock()
        self.call_receipts_path = Path(call_receipts_path) if call_receipts_path is not None else None
        self._statuses: dict[str, ConnectorStatus] = {}
        for cid, spec in self.specs.items():
            default_refresh = "not_applicable" if spec.auth_kind != "oauth2_refresh" else "fresh"
            configured = _is_configured(spec, self.env)
            self._statuses[cid] = ConnectorStatus(
                connector_id=cid,
                auth_status="configured_unverified" if configured else "unconfigured",
                granted_scopes=[],
                operations_available=[],
                health="unknown",
                last_verified_at=None,
                last_error=None,
                token_expires_at=None,
                refresh_state=default_refresh,
                checked_by="none",
            )

    def discover(self) -> dict[str, Any]:
        """Return connector metadata without exposing a registration/mutation path."""
        out: dict[str, Any] = {}
        for cid, connector in self._connectors.items():
            out[cid] = {
                "connector_id": cid,
                "health": {"health": "error"},
                "tools": [],
            }
            try:
                out[cid]["health"] = dict(connector.health())
                out[cid]["tools"] = json.loads(json.dumps(connector.tools()))
            except Exception:
                out[cid]["health"] = {"health": "error", "error": "connector discovery failed"}
        return out

    def _record_call(self, connector_id: str, tool_name: str, arguments: Any,
                     outcome: str, failure_kind: str | None, started: float) -> bool:
        try:
            canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except Exception:
            canonical = json.dumps({"unserializable_type": type(arguments).__name__}, sort_keys=True)
        receipt = {
            "connector_id": connector_id,
            "tool": tool_name,
            "outcome": outcome,
            "failure_kind": failure_kind,
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
            "timestamp": _utc_now_iso(),
            "arguments_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        }
        self.call_receipts.append(receipt)
        if self.call_receipts_path is None:
            return True
        try:
            path = self.call_receipts_path
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(receipt, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return True
        except Exception:
            # A configured durable audit sink is mandatory: callers must fail closed.
            return False

    @staticmethod
    def _validate_tool_arguments(schema: Any, arguments: Any) -> bool:
        if not isinstance(schema, Mapping) or not isinstance(arguments, dict):
            return False
        if schema.get("type") != "object":
            return False
        props = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(props, Mapping) or not isinstance(required, list):
            return False
        if any(k not in props for k in arguments) or any(k not in arguments for k in required):
            return False
        def matches(rule: Any, value: Any) -> bool:
            if not isinstance(rule, Mapping):
                return False
            typ = rule.get("type")
            checks = {
                "string": lambda x: isinstance(x, str),
                "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
                "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
                "boolean": lambda x: isinstance(x, bool),
                "object": lambda x: isinstance(x, dict),
                "array": lambda x: isinstance(x, list),
                "null": lambda x: x is None,
            }
            check = checks.get(typ)
            if check is None or not check(value):
                return False
            if "enum" in rule and value not in rule["enum"]:
                return False
            if typ == "object":
                nested_props = rule.get("properties", {})
                nested_required = rule.get("required", [])
                return (isinstance(nested_props, Mapping) and isinstance(nested_required, list)
                        and not any(k not in nested_props for k in value)
                        and not any(k not in value for k in nested_required)
                        and all(matches(nested_props[k], v) for k, v in value.items()))
            if typ == "array" and "items" in rule:
                return all(matches(rule["items"], item) for item in value)
            return True

        return all(matches(props[key], value) for key, value in arguments.items())

    def call(self, role: str, connector_id: str, tool_name: str, arguments: Any,
             task_allowlist: list[str] | set[str] | tuple[str, ...], timeout_s: float = 30,
             confirmed: bool = False) -> dict[str, Any]:
        started = time.monotonic()
        failure: str | None = None
        message = ""
        result: dict[str, Any] | None = None
        call_thread: threading.Thread | None = None
        call_invoked = False
        side_effects = "mutating"
        try:
            timeout = float(timeout_s)
            if timeout <= 0 or timeout > 120:
                timeout = 30.0
            connector = self._connectors.get(connector_id)
            if connector is None:
                failure, message = "unknown_connector", "Unknown connector"
            else:
                definitions = connector.tools()
                definition = next((x for x in definitions if isinstance(x, dict) and x.get("name") == tool_name), None)
                if definition is not None:
                    side_effects = definition.get("side_effects", "mutating")
                if definition is None:
                    failure, message = "unknown_tool", "Unknown tool"
                elif f"{connector_id}.{tool_name}" not in task_allowlist:  # connector-qualified: a bare tool name never matches
                    failure, message = "not_in_task_allowlist", "Tool is not in the task allowlist"
                else:
                    allowed, auth_message = authorize(role, connector_id, tool_name, self, confirmed=confirmed)
                    if not allowed:
                        failure = "unauthenticated" if "not verified" in auth_message else "not_authorized"
                        message = auth_message
                    elif not self._validate_tool_arguments(definition.get("input_schema"), arguments):
                        failure, message = "invalid_arguments", "Arguments do not match the tool input schema"
                    elif not getattr(connector, "cancellable", False):
                        failure, message = "uncancellable_connector", "Connector cannot be stopped on timeout; refused"
                    elif self._blocked_by_unknown(connector_id, tool_name, arguments):
                        failure, message = "execution_state_unknown", "A prior call has unknown execution state; not replayed"
                    else:
                        cancel = threading.Event()
                        responses: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)
                        def invoke() -> None:
                            nonlocal call_invoked
                            call_invoked = True
                            try:
                                responses.put((True, connector.call(tool_name, arguments, timeout_s=timeout, cancel=cancel)))
                            except BaseException as exc:
                                responses.put((False, exc))
                        thread = threading.Thread(target=invoke, daemon=True)
                        call_thread = thread
                        thread.start()
                        try:
                            ok, value = responses.get(timeout=timeout)
                            if not ok:
                                raise value
                            if not isinstance(value, dict):
                                raise TypeError("Connector result must be an object")
                            secrets = _collect_env_secrets({**os.environ, **self.env})
                            result = json.loads(redact(json.dumps(value, sort_keys=True), secrets))
                        except queue.Empty:
                            cancel.set()
                            thread.join(self.cancel_grace_s)
                            if thread.is_alive():
                                failure, message = "timeout_unknown_state", "Timed out; execution did not stop and its state is unknown"
                                self._mark_unknown(connector_id, tool_name, arguments, thread)
                            elif definition.get("side_effects") == "read_only":
                                failure, message = "timeout", "Read-only call timed out and execution stopped"
                            else:  # a mutating (or undeclared) call may have changed state before it honoured cancel
                                failure, message = "timeout_partial_unknown", "Timed out; execution stopped but partial effects are unknown"
                                self._mark_unknown(connector_id, tool_name, arguments, thread)
        except Exception as exc:
            failure = failure or "connector_error"
            message = message or str(exc)
            if call_invoked and side_effects != "read_only" and call_thread is not None:
                self._mark_unknown(connector_id, tool_name, arguments, call_thread)
                failure = "execution_state_unknown"
                message = "Connector failed after invocation; side effects are unknown and replay is blocked"
        if failure:
            secrets = _collect_env_secrets({**os.environ, **self.env})
            safe_message = redact(message, secrets)
            recorded = self._record_call(connector_id, tool_name, arguments, "FAIL", failure, started)
            if not recorded:
                if call_invoked and side_effects != "read_only" and call_thread is not None:
                    self._mark_unknown(connector_id, tool_name, arguments, call_thread)
                return {"status": "UNKNOWN" if call_invoked and side_effects != "read_only" else "FAIL",
                        "failure_kind": failure if failure == "execution_state_unknown" else "receipt_persistence_failed",
                        "error": "Execution remains unresolved; durable audit receipt could not be persisted"}
            return {"status": "FAIL", "failure_kind": failure, "error": safe_message}
        recorded = self._record_call(connector_id, tool_name, arguments, "SUCCESS", None, started)
        if not recorded:
            if call_invoked and side_effects != "read_only":
                self._mark_unknown(connector_id, tool_name, arguments, threading.current_thread())
                return {"status": "UNKNOWN", "failure_kind": "receipt_persistence_failed",
                        "error": "Action returned but its durable audit receipt failed; replay is blocked"}
            return {"status": "FAIL", "failure_kind": "receipt_persistence_failed",
                    "error": "Durable audit receipt could not be persisted"}
        return result or {}

    @staticmethod
    def _digest(connector_id: str, tool_name: str, arguments: Any) -> str:
        try:
            canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except Exception:
            canonical = repr(type(arguments))
        return hashlib.sha256(f"{connector_id}\0{tool_name}\0{canonical}".encode("utf-8")).hexdigest()

    def _mark_unknown(self, connector_id: str, tool_name: str, arguments: Any, thread: threading.Thread) -> None:
        with self._unknown_lock:
            self._unknown[self._digest(connector_id, tool_name, arguments)] = {
                "connector_id": connector_id, "tool": tool_name, "thread": thread}

    def _blocked_by_unknown(self, connector_id: str, tool_name: str, arguments: Any) -> bool:
        """Block replay of an unresolved call, and any call on a connector whose thread still runs."""
        with self._unknown_lock:
            if self._digest(connector_id, tool_name, arguments) in self._unknown:
                return True
            return any(v["connector_id"] == connector_id and v["thread"].is_alive() for v in self._unknown.values())

    def unresolved_calls(self) -> list[dict[str, Any]]:
        with self._unknown_lock:
            return [{"connector_id": v["connector_id"], "tool": v["tool"], "still_running": v["thread"].is_alive(),
                     "call_sha256": k} for k, v in self._unknown.items()]

    def resolve_unknown(self, call_sha256: str, operator_verified_effects: bool) -> bool:
        """Operator-only release of a replay block, and only after the thread ended and effects were checked."""
        with self._unknown_lock:
            entry = self._unknown.get(call_sha256)
            if entry is None or entry["thread"].is_alive() or operator_verified_effects is not True:
                return False
            del self._unknown[call_sha256]
            return True

    def status(self, connector_id: str, now: float | None = None) -> ConnectorStatus:
        if connector_id not in self.specs:
            raise KeyError(f"Unknown connector_id: {connector_id}")
        ts = time.time() if now is None else now
        spec = self.specs[connector_id]
        raw = self._statuses[connector_id]
        return _effective_status(spec, raw, self.env, ts, self.max_age_seconds)

    def all_statuses(self, now: float | None = None) -> dict[str, ConnectorStatus]:
        ts = time.time() if now is None else now
        return {cid: self.status(cid, now=ts) for cid in self.specs}

    def verify(self, connector_id: str, now: float | None = None) -> ConnectorStatus:
        if connector_id not in self.specs:
            raise KeyError(f"Unknown connector_id: {connector_id}")
        ts = time.time() if now is None else now
        spec = self.specs[connector_id]
        prev = self._statuses[connector_id]
        secrets = _collect_env_secrets(self.env, spec)
        checked_by = "local_probe" if spec.auth_kind == "local_none" else "verifier"

        if not _is_configured(spec, self.env):
            st = ConnectorStatus(
                connector_id=connector_id,
                auth_status="unconfigured",
                granted_scopes=[],
                operations_available=[],
                health="unconfigured",
                last_verified_at=None,
                last_error=None,
                token_expires_at=None,
                refresh_state="not_applicable" if spec.auth_kind != "oauth2_refresh" else "failed",
                checked_by=checked_by,
            )
            self._statuses[connector_id] = st
            return self.status(connector_id, now=ts)

        refresh_state = "not_applicable"
        if spec.auth_kind == "oauth2_refresh":
            had_prior_token = bool(prev.last_verified_at) or (connector_id in self._in_memory_tokens)
            if prev.token_expires_at is not None and prev.token_expires_at <= ts:
                refresh_state = "refreshed"
            elif prev.token_expires_at is not None and (prev.token_expires_at - ts) <= REFRESH_SKEW_SECONDS:
                refresh_state = "refreshed"
            elif had_prior_token:
                refresh_state = "refreshed"
            else:
                refresh_state = "fresh"

        verifier = self.verifiers.get(connector_id)
        if verifier is None:
            err = redact(f"No verifier registered for {connector_id}", secrets)
            st = ConnectorStatus(
                connector_id=connector_id,
                auth_status="error",
                granted_scopes=[],
                operations_available=[],
                health="unhealthy",
                last_verified_at=None,
                last_error=err,
                token_expires_at=prev.token_expires_at,
                refresh_state="failed" if spec.auth_kind == "oauth2_refresh" else "not_applicable",
                checked_by=checked_by,
            )
            self._statuses[connector_id] = st
            return self.status(connector_id, now=ts)

        try:
            ok, granted_scopes, expires_in, err_msg = verifier(self.env, self.http)
        except Exception as exc:
            safe_err = redact(str(exc), secrets)
            st = ConnectorStatus(
                connector_id=connector_id,
                auth_status="error",
                granted_scopes=[],
                operations_available=[],
                health="unhealthy",
                last_verified_at=None,
                last_error=safe_err,
                token_expires_at=None,
                refresh_state="failed" if spec.auth_kind == "oauth2_refresh" else "not_applicable",
                checked_by=checked_by,
            )
            self._statuses[connector_id] = st
            return self.status(connector_id, now=ts)

        def _resolve_expiry(raw_exp: float | None) -> float | None:
            if raw_exp is None:
                return None
            val = float(raw_exp)
            if val > 1_000_000_000.0 and ts < 1_000_000_000.0:
                return val
            return ts + val

        safe_granted = [str(s) for s in (granted_scopes or [])]
        if ok:
            resolved_exp = _resolve_expiry(expires_in)
            final_expires = resolved_exp if resolved_exp is not None else prev.token_expires_at
            if spec.auth_kind == "oauth2_refresh" and refresh_state == "not_applicable":
                refresh_state = "fresh"
            st = ConnectorStatus(
                connector_id=connector_id,
                auth_status="verified",
                granted_scopes=safe_granted,
                operations_available=list(spec.operations),
                health="healthy",
                last_verified_at=_utc_now_iso(ts),
                last_error=None,
                token_expires_at=final_expires,
                refresh_state=refresh_state,
                checked_by=checked_by,
            )
            self._statuses[connector_id] = st
            return self.status(connector_id, now=ts)

        safe_err = redact(err_msg or "Verification failed", secrets)
        is_expired = "expired" in safe_err.lower() or (
            spec.auth_kind == "oauth2_refresh" and prev.token_expires_at is not None and prev.token_expires_at <= ts
        )
        resolved_err_exp = _resolve_expiry(expires_in)
        st = ConnectorStatus(
            connector_id=connector_id,
            auth_status="expired" if is_expired else "error",
            granted_scopes=safe_granted,
            operations_available=[],
            health="unhealthy",
            last_verified_at=None,
            last_error=safe_err,
            token_expires_at=resolved_err_exp if resolved_err_exp is not None else prev.token_expires_at,
            refresh_state="failed" if spec.auth_kind == "oauth2_refresh" else "not_applicable",
            checked_by=checked_by,
        )
        self._statuses[connector_id] = st
        return self.status(connector_id, now=ts)

    def verify_all(self, now: float | None = None) -> dict[str, ConnectorStatus]:
        ts = time.time() if now is None else now
        return {cid: self.verify(cid, now=ts) for cid in self.specs}

    def health_report(self, now: float | None = None) -> dict[str, Any]:
        ts = time.time() if now is None else now
        statuses = self.all_statuses(now=ts)
        summary: dict[str, int] = {k: 0 for k in AUTH_STATUSES}
        connectors_out: dict[str, dict[str, Any]] = {}
        for cid, st in statuses.items():
            summary[st.auth_status] = summary.get(st.auth_status, 0) + 1
            connectors_out[cid] = st.to_dict()
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _utc_now_iso(ts),
            "total": len(statuses),
            "counts_by_auth_status": summary,
            "connectors": connectors_out,
        }

    def persist(self, path: str | os.PathLike[str], now: float | None = None) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        ts = time.time() if now is None else now
        secrets = _collect_env_secrets(self.env)

        items: dict[str, dict[str, Any]] = {}
        for cid in self.specs:
            st = self.status(cid, now=ts)
            d = st.to_dict()
            if d.get("last_error"):
                d["last_error"] = redact(str(d["last_error"]), secrets)
            items[cid] = d

        payload = {
            "schema_version": SCHEMA_VERSION,
            "statuses": items,
        }
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        safe_serialized = redact(serialized, secrets)

        fd, tmp_name = tempfile.mkstemp(prefix=".receipts_", suffix=".tmp", dir=str(target.parent))
        tmp_path = Path(tmp_name)
        try:
            os.chmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(safe_serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, target)
            os.chmod(target, 0o600)
        except Exception:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise

    def load(self, path: str | os.PathLike[str]) -> dict[str, ConnectorStatus]:
        target = Path(path)
        raw_text = target.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("Invalid receipt payload: expected object")
        version = data.get("schema_version")
        if version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported receipt schema_version: {version}")
        raw_statuses = data.get("statuses")
        if not isinstance(raw_statuses, dict):
            raise ValueError("Invalid receipt payload: missing statuses object")

        loaded: dict[str, ConnectorStatus] = {}
        for cid, entry in raw_statuses.items():
            if cid in self.specs and isinstance(entry, dict):
                st = ConnectorStatus.from_dict(entry)
                if st.auth_status == "verified" and not st.last_verified_at:
                    st.auth_status = "configured_unverified"
                self._statuses[cid] = st
                loaded[cid] = st
        return loaded


def authorize(
    role: str,
    connector_id: str,
    operation: str,
    registry: ConnectorRegistry,
    now: float | None = None,
    confirmed: bool = False,
) -> tuple[bool, str]:
    ts = time.time() if now is None else now
    allowed_patterns = ROLES.get(role)
    if not allowed_patterns:
        return False, f"Unknown or unauthorized role: {role}"

    matched = any(
        fnmatch.fnmatchcase(connector_id, c_pat) and fnmatch.fnmatchcase(operation, op_pat)
        for c_pat, op_pat in allowed_patterns
    )
    if not matched:
        return False, f"Role {role} is not permitted to run {operation} on {connector_id}"

    if connector_id not in registry.specs:
        return False, f"Unknown connector: {connector_id}"

    spec = registry.specs[connector_id]
    if operation not in spec.operations:
        return False, f"Operation {operation} is not supported by {connector_id}"

    st = registry.status(connector_id, now=ts)
    if st.auth_status != "verified":
        return False, f"Connector {connector_id} is not verified (status={st.auth_status})"

    required_scopes = list(spec.scopes_required)
    op_scopes = spec.operation_scopes.get(operation, [])
    for sc in op_scopes:
        if sc not in required_scopes:
            required_scopes.append(sc)

    if required_scopes:
        granted_set = set(st.granted_scopes)
        missing = [sc for sc in required_scopes if sc not in granted_set]
        if missing:
            return False, f"Missing required scopes for {operation}: {', '.join(missing)}"

    if is_destructive_operation(operation) and not confirmed:
        return False, f"Destructive operation {operation} requires confirmed=True"

    return True, "Allowed"


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Blind Sniper Connector Registry CLI")
    parser.add_argument("command", choices=["status", "verify"], help="Action to perform")
    parser.add_argument("connector_id", nargs="?", default=None, help="Optional target connector_id")
    parser.add_argument("--receipts", default=None, help="Path to receipts JSON file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
        return 0 if code == 0 else 2

    try:
        registry = ConnectorRegistry()
        if args.receipts:
            receipt_path = Path(args.receipts)
            if receipt_path.exists():
                registry.load(receipt_path)

        if args.connector_id and args.connector_id not in registry.specs:
            print(json.dumps({"error": f"Unknown connector_id: {args.connector_id}"}, indent=2))
            return 2

        if args.command == "status":
            if args.connector_id:
                st = registry.status(args.connector_id)
                print(json.dumps(st.to_dict(), indent=2, sort_keys=True))
                return 0 if st.auth_status == "verified" else 1
            all_st = registry.all_statuses()
            print(json.dumps({k: v.to_dict() for k, v in all_st.items()}, indent=2, sort_keys=True))
            return 0 if all(v.auth_status == "verified" for v in all_st.values()) else 1

        if args.command == "verify":
            if args.connector_id:
                st = registry.verify(args.connector_id)
                if args.receipts:
                    registry.persist(args.receipts)
                print(json.dumps(st.to_dict(), indent=2, sort_keys=True))
                return 0 if st.auth_status == "verified" else 1
            verified_map = registry.verify_all()
            if args.receipts:
                registry.persist(args.receipts)
            print(json.dumps({k: v.to_dict() for k, v in verified_map.items()}, indent=2, sort_keys=True))
            return 0 if all(v.auth_status == "verified" for v in verified_map.values()) else 1

        return 2
    except Exception as exc:
        safe_msg = redact(str(exc), _collect_env_secrets(dict(os.environ)))
        print(json.dumps({"error": safe_msg}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
