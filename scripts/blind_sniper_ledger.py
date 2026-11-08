#!/usr/bin/env python3
"""Native append-only task event ledger for Blind Sniper.

This is a durable local-workspace store, not a claim of cross-runner storage.
Cross-session/cloud durability requires a persistent workspace or a future
GitHub-backed compare-and-swap adapter.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LedgerError(ValueError):
    """Invalid, corrupt, or conflicting ledger operation."""


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


class TaskLedger:
    """Hash-chained JSONL event store with process locking and idempotent writes."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        previous_hash = "GENESIS"
        previous_seq = 0
        for line_number, raw in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise LedgerError(f"Corrupt JSON at line {line_number}") from exc
            if not isinstance(event, dict):
                raise LedgerError(f"Invalid event at line {line_number}")
            supplied_hash = event.pop("event_hash", None)
            if event.get("prev_hash") != previous_hash:
                raise LedgerError(f"Broken hash chain at line {line_number}")
            if event.get("seq") != previous_seq + 1:
                raise LedgerError(f"Invalid sequence at line {line_number}")
            if supplied_hash != _digest(event):
                raise LedgerError(f"Event hash mismatch at line {line_number}")
            event["event_hash"] = supplied_hash
            events.append(event)
            previous_hash = supplied_hash
            previous_seq += 1
        return events

    def events(self, task_id: str | None = None) -> list[dict[str, Any]]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                rows = self._read_unlocked()
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return [row for row in rows if task_id is None or row["task_id"] == task_id]

    def append(
        self,
        *,
        task_id: str,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if not task_id.strip() or not event_type.strip() or not idempotency_key.strip():
            raise LedgerError("task_id, event_type and idempotency_key are required")
        if not isinstance(payload, dict):
            raise LedgerError("payload must be an object")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                rows = self._read_unlocked()
                for row in rows:
                    if row["idempotency_key"] == idempotency_key:
                        if row["task_id"] != task_id or row["event_type"] != event_type or row["payload"] != payload:
                            raise LedgerError("idempotency key already used for different event content")
                        return row
                previous_hash = rows[-1]["event_hash"] if rows else "GENESIS"
                body = {
                    "schema_version": "1.0.0",
                    "seq": len(rows) + 1,
                    "task_id": task_id,
                    "event_type": event_type,
                    "idempotency_key": idempotency_key,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "payload": payload,
                    "prev_hash": previous_hash,
                }
                event = {**body, "event_hash": _digest(body)}
                handle.seek(0, os.SEEK_END)
                handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                return event
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def task_history(self, task_id: str) -> dict[str, Any]:
        rows = self.events(task_id)
        if not rows:
            raise LedgerError(f"Unknown task_id: {task_id}")
        return {
            "task_id": task_id,
            "event_count": len(rows),
            "last_event": rows[-1],
            "events": rows,
        }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Blind Sniper durable task event ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("append", help="append one idempotent task event")
    add.add_argument("--ledger", required=True)
    add.add_argument("--task-id", required=True)
    add.add_argument("--event-type", required=True)
    add.add_argument("--idempotency-key", required=True)
    add.add_argument("--payload-file", required=True)
    show = sub.add_parser("show", help="verify and display task history")
    show.add_argument("--ledger", required=True)
    show.add_argument("--task-id", required=True)
    args = parser.parse_args(argv)
    try:
        ledger = TaskLedger(args.ledger)
        if args.command == "append":
            payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
            event = ledger.append(task_id=args.task_id, event_type=args.event_type,
                                  payload=payload, idempotency_key=args.idempotency_key)
            print(json.dumps({"task_id": args.task_id, "seq": event["seq"],
                              "event_hash": event["event_hash"]}, indent=2))
        else:
            print(json.dumps(ledger.task_history(args.task_id), indent=2, ensure_ascii=False))
        return 0
    except (LedgerError, OSError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
