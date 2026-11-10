#!/usr/bin/env python3
"""Deterministic secret redaction for receipts, logs and error surfaces.

The patterns are the ones that have actually appeared in this project's
evidence (Fernet blobs, OpenAI-style keys, GitHub tokens, Google/Gemini keys,
private keys and credentials embedded in URLs). Callers may also pass explicit
secret values (for example a token read from the environment) so that the exact
value is removed even when it matches no generic pattern.

This module never reads credentials itself and never writes anything.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

REDACTED = "[REDACTED]"

_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"gAAAAA[A-Za-z0-9_\-=]{10,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"AQ\.[A-Za-z0-9_\-]{40,}"),
    re.compile(r"https://[^\s/@:]+:[^\s/@]+@", re.IGNORECASE),
    re.compile(r"(?i)\b(bearer|token|api[_-]?key|secret|password)\b\s*[:=]\s*[A-Za-z0-9._\-]{12,}"),
)


def redact_text(value: str, secrets: Iterable[str] | None = None) -> str:
    """Return *value* with recognised secret patterns and explicit secrets removed."""
    if not isinstance(value, str):
        value = str(value)
    for secret in secrets or ():
        if secret and len(str(secret)) >= 8:
            value = value.replace(str(secret), REDACTED)
    for pattern in _PATTERNS:
        value = pattern.sub(REDACTED, value)
    return value


def redact(value: Any, secrets: Iterable[str] | None = None) -> Any:
    """Recursively redact strings inside dicts, lists, tuples and scalars."""
    secret_list = tuple(secrets) if secrets else None
    if isinstance(value, str):
        return redact_text(value, secret_list)
    if isinstance(value, dict):
        return {key: redact(item, secret_list) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, secret_list) for item in value]
    return value
