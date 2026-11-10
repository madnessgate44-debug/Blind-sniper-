#!/usr/bin/env python3
"""Shared secret redaction for adapter receipts, logs and digests.

Every adapter that can observe a credential (OpenHands Cloud, Forge MCP, the
queue worker) routes observable text and structured payloads through this
module before it is written to a receipt, artifact or ledger event. Redaction
is best-effort pattern matching; it is a defence in depth, not a guarantee.
"""
from __future__ import annotations

import re
from typing import Any

PLACEHOLDER = "[REDACTED]"

# Order matters: more specific patterns first so a broad token rule cannot
# swallow a longer, more descriptive match.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    )),
    ("bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b")),
    ("openai", re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b")),
    ("google_api", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("gemini_oauth", re.compile(r"\bAQ\.[A-Za-z0-9_-]{40,}\b")),
    ("fernet", re.compile(r"\bgAAAAA[A-Za-z0-9_-]{16,}={0,2}\b")),
    ("slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("json_secret", re.compile(
        r'"(?:api[_-]?key|token|secret|password|authorization|session[_-]?api[_-]?key)"'
        r'\s*:\s*"[^"]*"',
        re.IGNORECASE,
    )),
)

_SENSITIVE_HEADERS = frozenset({
    "authorization",
    "proxy-authorization",
    "x-session-api-key",
    "x-api-key",
    "api-key",
    "cookie",
    "set-cookie",
})


def redact_text(value: str) -> str:
    """Return *value* with recognized credential patterns replaced."""
    if not isinstance(value, str):
        return value
    redacted = value
    for _name, pattern in _PATTERNS:
        redacted = pattern.sub(PLACEHOLDER, redacted)
    return redacted


def redact_headers(headers: dict[str, Any] | None) -> dict[str, Any]:
    """Return a copy of *headers* with sensitive header values masked."""
    if not headers:
        return {}
    return {
        str(key): (PLACEHOLDER if str(key).strip().lower() in _SENSITIVE_HEADERS else redact_value(value))
        for key, value in headers.items()
    }


def redact_value(value: Any) -> Any:
    """Recursively redact strings inside dicts, lists and scalars."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {key: redact_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    return value


def contains_secret(value: Any) -> bool:
    """Report whether any known credential pattern is present in *value*."""
    if isinstance(value, str):
        return redact_text(value) != value
    if isinstance(value, dict):
        return any(contains_secret(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_secret(item) for item in value)
    return False
