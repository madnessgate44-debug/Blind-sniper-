#!/usr/bin/env python3
"""Crash-safe bridge from model-authored handoffs to native private task files."""
from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from blind_sniper_memory_handoff import (
    HandoffError,
    claim_handoff,
    list_handoffs,
    recover_native_handoff,
)

MAX_HANDOFF_DEPTH = 4
MAX_TASK_BYTES = 2 * 1024 * 1024


class HandoffRuntimeError(RuntimeError):
    """Native handoff delivery or private task materialization failure."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _ensure_private_task_dir(path: Path) -> Path:
    if path.is_symlink():
        raise HandoffRuntimeError("private task directory cannot be a symlink")
    resolved = path.resolve(strict=True)
    info = resolved.stat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise HandoffRuntimeError("private task directory must be owner-only (0700)")
    return resolved


def _write_task_once(task_dir: Path, task: dict[str, Any]) -> str:
    task_id = task["task_id"]
    target = task_dir / f"{task_id}.json"
    encoded = _canonical(task) + b"\n"
    if len(encoded) > MAX_TASK_BYTES:
        raise HandoffRuntimeError("handoff continuation task exceeds the private task size limit")
    try:
        info = target.lstat()
    except FileNotFoundError:
        info = None
    if info is not None:
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077 or info.st_nlink != 1:
            raise HandoffRuntimeError("existing continuation task is not a private regular file")
        existing = json.loads(target.read_text(encoding="utf-8"))
        if existing != task:
            raise HandoffRuntimeError("continuation task ID already exists with different content")
        return "EXISTS"
    fd, temporary = tempfile.mkstemp(prefix=".handoff-task-", dir=str(task_dir))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            existing = json.loads(target.read_text(encoding="utf-8"))
            if existing != task:
                raise HandoffRuntimeError("continuation task ID raced with different content")
            return "EXISTS"
        directory_fd = os.open(task_dir, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return "CREATED"
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def reconcile_handoffs(
    *,
    handoff_dir: Path,
    task_dir: Path,
    queue: Any,
    allowed_agent_ids: frozenset[str],
    limit: int = 10,
) -> dict[str, int]:
    """Deliver claimed handoffs as idempotent child tasks after parent completion.

    Claim-before-materialize is recoverable: a later poll may repeat the same
    claim for the same recipient and reconstruct the same deterministic child.
    """
    if not 1 <= limit <= 100:
        raise HandoffRuntimeError("handoff reconciliation limit must be between 1 and 100")
    root = _ensure_private_task_dir(task_dir)
    counts = {"scanned": 0, "delivered": 0, "pending": 0}
    packets = list_handoffs(handoff_dir)
    for packet in packets[:limit]:
        counts["scanned"] += 1
        recipient = packet["to_agent"]
        if recipient not in allowed_agent_ids:
            raise HandoffRuntimeError("handoff recipient is not registered in the native agent roster")
        parent_state = queue.status(packet["task_id"])
        if not isinstance(parent_state, dict) or parent_state.get("status") != "COMPLETED":
            counts["pending"] += 1
            continue
        if packet["handoff_depth"] >= MAX_HANDOFF_DEPTH:
            raise HandoffRuntimeError("handoff chain reached the configured depth limit")
        claim_handoff(handoff_dir, packet["handoff_id"], recipient)
        recovered = recover_native_handoff(
            handoff_dir, packet["handoff_id"], recipient, queue=queue,
        )
        child_id = "handoff-" + __import__("hashlib").sha256(
            packet["handoff_id"].encode("utf-8")
        ).hexdigest()[:32]
        child = {
            "task_id": child_id,
            "agent_id": recipient,
            "objective": packet["next_action"],
            "payload": {
                "handoff": recovered["handoff"],
                "current_task_state": recovered["current_task_state"],
                "approved_knowledge": recovered["approved_knowledge"],
                "handoff_depth": packet["handoff_depth"] + 1,
            },
        }
        outcome = _write_task_once(root, child)
        if outcome == "CREATED":
            counts["delivered"] += 1
    return counts
