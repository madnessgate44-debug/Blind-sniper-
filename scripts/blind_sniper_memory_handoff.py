#!/usr/bin/env python3
"""Typed private handoffs with atomic claim-once and ledger-authoritative recovery."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from blind_sniper_memory import MemoryError, _ensure_private_external_path
from blind_sniper_redact import redact

HANDOFF_FIELDS = {
    "handoff_id", "task_id", "from_agent", "to_agent", "created_at",
    "objective", "verified_state", "open_questions", "files_touched",
    "evidence_refs", "next_action", "claim_state",
}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")
SAFE_PATH = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9_.@/-]{1,240}$")


class HandoffError(ValueError):
    """Invalid handoff, claim conflict or recovery failure."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_handoff(
    *,
    handoff_id: str,
    task_id: str,
    from_agent: str,
    to_agent: str,
    created_at: str,
    objective: str,
    verified_state: dict[str, Any],
    open_questions: list[str],
    files_touched: list[str],
    evidence_refs: list[str],
    next_action: str,
    claim_state: str = "unclaimed",
) -> dict[str, Any]:
    """Validate a bounded, redacted handoff packet without storing task prompts."""
    for label, value in (("handoff_id", handoff_id), ("task_id", task_id), ("from_agent", from_agent), ("to_agent", to_agent)):
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
            raise HandoffError(f"{label} is invalid")
    if from_agent == to_agent:
        raise HandoffError("from_agent and to_agent must differ")
    try:
        instant = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise HandoffError("created_at must be timezone-aware ISO-8601") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise HandoffError("created_at must be timezone-aware ISO-8601")
    if claim_state != "unclaimed":
        raise HandoffError("new handoffs must begin unclaimed")
    if not isinstance(objective, str) or not objective.strip() or len(objective) > 1000:
        raise HandoffError("objective must be a non-empty bounded string")
    if not isinstance(next_action, str) or not next_action.strip() or len(next_action) > 1000:
        raise HandoffError("next_action must be a non-empty bounded string")
    if not isinstance(verified_state, dict) or set(verified_state) - {"status", "attempt", "receipt_digest", "last_event"}:
        raise HandoffError("verified_state contains unsupported fields")
    if not isinstance(verified_state.get("status"), str) or len(verified_state["status"]) > 64:
        raise HandoffError("verified_state.status is required")
    if "attempt" in verified_state and (
        isinstance(verified_state["attempt"], bool) or not isinstance(verified_state["attempt"], int)
        or verified_state["attempt"] < 0
    ):
        raise HandoffError("verified_state.attempt must be a non-negative integer")
    if "receipt_digest" in verified_state and not DIGEST.fullmatch(str(verified_state["receipt_digest"])):
        raise HandoffError("verified_state.receipt_digest must be SHA-256")
    if "last_event" in verified_state and (
        not isinstance(verified_state["last_event"], str) or len(verified_state["last_event"]) > 128
    ):
        raise HandoffError("verified_state.last_event is invalid")
    for label, values, limit, max_len in (
        ("open_questions", open_questions, 10, 500),
        ("files_touched", files_touched, 50, 240),
        ("evidence_refs", evidence_refs, 20, 512),
    ):
        if not isinstance(values, list) or len(values) > limit or any(not isinstance(v, str) or not v.strip() or len(v) > max_len for v in values):
            raise HandoffError(f"{label} must be a bounded string array")
    if any(not SAFE_PATH.fullmatch(path) for path in files_touched):
        raise HandoffError("files_touched must contain safe repository-relative paths")
    packet = {
        "handoff_id": handoff_id,
        "task_id": task_id,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "created_at": instant.astimezone(timezone.utc).isoformat(),
        "objective": redact(objective.strip()),
        "verified_state": redact(verified_state),
        "open_questions": redact(open_questions),
        "files_touched": files_touched,
        "evidence_refs": redact(evidence_refs),
        "next_action": redact(next_action.strip()),
        "claim_state": "unclaimed",
    }
    if len(_canonical(packet)) > 16 * 1024:
        raise HandoffError("handoff packet exceeds 16 KiB")
    return packet


def _read_private_json(path: Path) -> dict[str, Any]:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise HandoffError("private handoff record does not exist") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o077:
        raise HandoffError("private handoff records must be owner-only regular files")
    if info.st_size > 16 * 1024:
        raise HandoffError("private handoff record exceeds 16 KiB")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError("private handoff record is invalid") from exc
    if not isinstance(value, dict):
        raise HandoffError("private handoff record must be a JSON object")
    return value


def _private_directory(path: str | Path) -> Path:
    directory = Path(path).expanduser().absolute()
    probe = _ensure_private_external_path(directory / ".handoff-probe")
    resolved = probe.parent
    if not resolved.is_dir() or stat.S_IMODE(resolved.stat().st_mode) & 0o077:
        raise HandoffError("handoff directory must be owner-only (0700)")
    return resolved


def write_handoff(directory: str | Path, packet: dict[str, Any]) -> str:
    if not isinstance(packet, dict) or set(packet) != HANDOFF_FIELDS:
        raise HandoffError("handoff packet does not match the closed schema")
    try:
        validated = build_handoff(**packet)
    except (TypeError, ValueError) as exc:
        raise HandoffError("handoff packet failed schema validation") from exc
    if validated != packet:
        raise HandoffError("handoff packet is not canonical or sanitized")
    root = _private_directory(directory)
    path = _ensure_private_external_path(root / f"{packet['handoff_id']}.json")
    payload = _canonical(packet) + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        existing = _read_private_json(path)
        if existing == packet:
            return "DUPLICATE"
        raise HandoffError("handoff_id already exists with different content")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return "CREATED"


def claim_handoff(directory: str | Path, handoff_id: str, agent_id: str) -> str:
    if not IDENTIFIER.fullmatch(handoff_id) or not IDENTIFIER.fullmatch(agent_id):
        raise HandoffError("handoff_id or agent_id is invalid")
    root = _private_directory(directory)
    packet_path = root / f"{handoff_id}.json"
    if not packet_path.is_file() or packet_path.is_symlink():
        raise HandoffError("handoff does not exist")
    info = packet_path.stat()
    if stat.S_IMODE(info.st_mode) & 0o077 or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise HandoffError("handoff file must be owner-only and singly linked")
    packet = _read_private_json(packet_path)
    try:
        if build_handoff(**packet) != packet:
            raise HandoffError("handoff packet is not canonical")
    except (TypeError, ValueError) as exc:
        raise HandoffError("handoff packet failed schema validation") from exc
    if packet.get("handoff_id") != handoff_id or packet.get("to_agent") != agent_id:
        raise HandoffError("handoff is not assigned to this agent")
    claim_path = _ensure_private_external_path(root / f"{handoff_id}.claim.json")
    claim = {
        "handoff_id": handoff_id,
        "agent_id": agent_id,
        "claimed_at": datetime.now(timezone.utc).isoformat(),
        "packet_digest": hashlib.sha256(_canonical(packet)).hexdigest(),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(claim_path, flags, 0o600)
    except FileExistsError:
        existing = _read_private_json(claim_path)
        if existing.get("agent_id") == agent_id and existing.get("packet_digest") == claim["packet_digest"]:
            return "ALREADY_CLAIMED"
        raise HandoffError("handoff has already been claimed")
    with os.fdopen(fd, "wb") as handle:
        handle.write(_canonical(claim) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    return "CLAIMED"


def recover_handoff(
    directory: str | Path,
    handoff_id: str,
    agent_id: str,
    *,
    task_state_reader: Callable[[str], dict[str, Any] | None],
    approved_knowledge_reader: Callable[[str], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Re-read authoritative task state; attach only caller-supplied approved knowledge."""
    root = _private_directory(directory)
    packet_path = root / f"{handoff_id}.json"
    claim_path = root / f"{handoff_id}.claim.json"
    if (
        not packet_path.is_file() or not claim_path.is_file()
        or packet_path.is_symlink() or claim_path.is_symlink()
    ):
        raise HandoffError("handoff must exist and be claimed before recovery")
    packet = _read_private_json(packet_path)
    try:
        if build_handoff(**packet) != packet:
            raise HandoffError("handoff packet is not canonical")
    except (TypeError, ValueError) as exc:
        raise HandoffError("handoff packet failed schema validation") from exc
    claim = _read_private_json(claim_path)
    if claim.get("packet_digest") != hashlib.sha256(_canonical(packet)).hexdigest():
        raise HandoffError("handoff claim does not match the packet digest")
    if claim.get("agent_id") != agent_id or packet.get("to_agent") != agent_id:
        raise HandoffError("recovery caller does not own this handoff claim")
    current = task_state_reader(packet["task_id"])
    if not isinstance(current, dict):
        raise HandoffError("authoritative task ledger did not return current task state")
    knowledge = approved_knowledge_reader(packet["task_id"]) if approved_knowledge_reader else []
    if not isinstance(knowledge, list) or any(not isinstance(item, dict) or item.get("status") != "approved" for item in knowledge):
        raise HandoffError("approved knowledge reader returned non-approved or invalid records")
    return {
        "handoff": packet,
        "current_task_state": current,
        "approved_knowledge": knowledge,
        "task_state_source": "native_task_ledger",
    }

def recover_native_handoff(
    directory: str | Path,
    handoff_id: str,
    agent_id: str,
    *,
    queue: Any,
    approved_knowledge_reader: Callable[[str], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Recover using the native DurableQueue.status ledger read path."""
    status_reader = getattr(queue, "status", None)
    if not callable(status_reader):
        raise HandoffError("native queue must expose status(task_id)")
    return recover_handoff(
        directory,
        handoff_id,
        agent_id,
        task_state_reader=status_reader,
        approved_knowledge_reader=approved_knowledge_reader,
    )
