#!/usr/bin/env python3
"""Privacy-gated local observation journal for Blind Sniper memory.

This is a storage primitive, not an automatic capture hook or hosted service.
The journal must live outside the repository checkout.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blind_sniper_redact import redact  # noqa: E402

SCHEMA_VERSION = "1.0.0"
CAPTURE_POLICY_VERSION = "1.0.0"
MAX_CONTENT_BYTES = 8 * 1024
MAX_JOURNAL_BYTES = 20 * 1024 * 1024
ALLOWED_EVENT_TYPES = {
    "task_created",
    "task_transition",
    "execution_receipt",
    "verification_result",
    "agent_finding",
    "handoff_created",
}
ALLOWED_SOURCES = {
    "blind_sniper_runtime",
    "blind_sniper_daemon",
    "blind_sniper_executor",
    "github_actions",
}
ALLOWED_CLASSIFICATIONS = {"public_project", "private_owner"}
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SENSITIVE_KEYS = {
    "password", "passwd", "token", "access_token", "refresh_token",
    "api_key", "apikey", "secret", "private_key", "authorization",
    "cookie", "set_cookie", "credential", "credentials",
}


class MemoryError(ValueError):
    """Invalid, unsafe, or conflicting memory operation."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _reject_sensitive_keys(value: Any, path: str = "content") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in {re.sub(r"[^a-z0-9]", "", k) for k in SENSITIVE_KEYS}:
                raise MemoryError(f"sensitive field is not eligible for memory: {path}.{key}")
            _reject_sensitive_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_sensitive_keys(item, f"{path}[{index}]")


def _validate_timestamp(value: str) -> None:
    if not isinstance(value, str):
        raise MemoryError("occurred_at must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MemoryError("occurred_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MemoryError("occurred_at must include a timezone")


def build_observation(
    *,
    observation_id: str,
    event_type: str,
    occurred_at: str,
    source: str,
    source_ref: str,
    project_id: str,
    classification: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    """Validate, sanitize and construct a closed observation record."""
    if not isinstance(observation_id, str) or not ID_RE.fullmatch(observation_id):
        raise MemoryError("invalid observation_id")
    if event_type not in ALLOWED_EVENT_TYPES:
        raise MemoryError("event_type is not allowlisted")
    if source not in ALLOWED_SOURCES:
        raise MemoryError("source is not allowlisted")
    if not isinstance(source_ref, str) or not source_ref or len(source_ref) > 512:
        raise MemoryError("source_ref must be a non-empty bounded string")
    source_ref = redact(source_ref)
    if not isinstance(project_id, str) or not PROJECT_RE.fullmatch(project_id):
        raise MemoryError("invalid project_id")
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise MemoryError("classification is not eligible for capture")
    _validate_timestamp(occurred_at)
    if not isinstance(content, dict):
        raise MemoryError("content must be a JSON object")
    _reject_sensitive_keys(content)
    sanitized = redact(content)
    try:
        encoded = _canonical(sanitized)
    except (TypeError, ValueError) as exc:
        raise MemoryError("content must contain JSON-compatible values") from exc
    if len(encoded) > MAX_CONTENT_BYTES:
        raise MemoryError(f"content exceeds {MAX_CONTENT_BYTES} bytes")
    record = {
        "schema_version": SCHEMA_VERSION,
        "observation_id": observation_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "source": source,
        "source_ref": source_ref,
        "project_id": project_id,
        "classification": classification,
        "content": sanitized,
        "content_digest": hashlib.sha256(encoded).hexdigest(),
        "capture_policy_version": CAPTURE_POLICY_VERSION,
    }
    return record


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_private_external_path(journal_path: str | Path) -> Path:
    target = Path(journal_path).expanduser().absolute()
    repo = _repository_root()
    # Reject lexically before mkdir so a refused path cannot create anything
    # inside the public checkout as a side effect.
    try:
        target.relative_to(repo)
    except ValueError:
        pass
    else:
        raise MemoryError("memory journal must be outside the repository checkout")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved_parent = target.parent.resolve(strict=True)
    resolved = resolved_parent / target.name
    try:
        resolved.relative_to(repo)
    except ValueError:
        pass
    else:
        raise MemoryError("memory journal must be outside the repository checkout")
    if resolved.exists() and resolved.is_symlink():
        raise MemoryError("journal symlinks are not permitted")
    return resolved


def append_observation(journal_path: str | Path, record: dict[str, Any]) -> str:
    """Append once to a private external JSONL journal; return APPENDED or DUPLICATE."""
    expected = {
        "schema_version", "observation_id", "event_type", "occurred_at",
        "source", "source_ref", "project_id", "classification", "content",
        "content_digest", "capture_policy_version",
    }
    if not isinstance(record, dict) or set(record) != expected:
        raise MemoryError("observation record does not match the closed schema")
    rebuilt = build_observation(
        observation_id=record["observation_id"],
        event_type=record["event_type"],
        occurred_at=record["occurred_at"],
        source=record["source"],
        source_ref=record["source_ref"],
        project_id=record["project_id"],
        classification=record["classification"],
        content=record["content"],
    )
    if rebuilt != record:
        raise MemoryError("observation digest or sanitized content mismatch")

    path = _ensure_private_external_path(journal_path)
    flags = os.O_CREAT | os.O_RDWR | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "r+", encoding="utf-8", closefd=False) as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            stream.seek(0, os.SEEK_END)
            current_size = stream.tell()
            if current_size > MAX_JOURNAL_BYTES:
                raise MemoryError("memory journal size limit exceeded")
            stream.seek(0)
            for line in stream:
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise MemoryError("memory journal contains corrupt JSON") from exc
                if existing.get("observation_id") == record["observation_id"]:
                    if existing != record:
                        raise MemoryError("observation_id collision with different content")
                    return "DUPLICATE"
            payload = _canonical(record) + b"\n"
            if current_size + len(payload) > MAX_JOURNAL_BYTES:
                raise MemoryError("memory journal size limit exceeded")
            stream.seek(0, os.SEEK_END)
            stream.write(payload.decode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
            return "APPENDED"
    finally:
        os.close(fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and append one Blind Sniper memory observation")
    parser.add_argument("--input", required=True, help="JSON observation input")
    parser.add_argument("--journal", required=True, help="Private JSONL journal path outside the repository")
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        record = build_observation(**data)
        result = append_observation(args.journal, record)
    except (OSError, json.JSONDecodeError, TypeError, KeyError, MemoryError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result, "observation_id": record["observation_id"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
