#!/usr/bin/env python3
"""Durable queue / claim / lease / heartbeat / cancel / recovery protocol.

The queue is a *logical* durable protocol, not a continuously resident process.
It persists as append-only events in the same native ledger used by the runtime
(``TaskLedger`` locally, ``GitHubContentsLedger`` against a private repository).
Because every event carries a monotonic ``seq`` and the backends guarantee a
total order (file lock locally, blob-SHA compare-and-swap remotely), the queue
survives independent GitHub Actions runs: a later run replays the ledger and
observes the same task state.

Contention is resolved first-writer-wins by sequence: a claim appends a
``QUEUE_TASK_CLAIMED`` event, then re-reads the ledger and only reports success
if its own event is the earliest claim for that attempt. This needs no extra
lock beyond the backend's atomic append.

Private task payloads never enter the ledger. ``enqueue`` accepts only a
``payload_ref`` (a key into private storage) and a ``payload_hash``; the body is
never written here.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

ENQUEUED = "QUEUE_TASK_ENQUEUED"
CLAIMED = "QUEUE_TASK_CLAIMED"
HEARTBEAT = "QUEUE_TASK_HEARTBEAT"
RELEASED = "QUEUE_TASK_RELEASED"
RECLAIMED = "QUEUE_TASK_RECLAIMED"
COMPLETED = "QUEUE_TASK_COMPLETED"
FAILED = "QUEUE_TASK_FAILED"
CANCELLED = "QUEUE_TASK_CANCELLED"

EVENT_TYPES = (ENQUEUED, CLAIMED, HEARTBEAT, RELEASED, RECLAIMED, COMPLETED, FAILED, CANCELLED)
# Terminal *status* values (the replay state uses short names, not event names).
TERMINAL = ("COMPLETED", "FAILED", "CANCELLED")

MIN_LEASE_SECONDS = 1
MAX_LEASE_SECONDS = 3600


class QueueError(ValueError):
    """Invalid or conflicting durable-queue operation."""


def _parse_instant(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise QueueError(f"{label} must be an ISO-8601 instant") from exc
    if parsed.tzinfo is None:
        raise QueueError(f"{label} must include a timezone")
    return parsed


def _require_id(value: str, label: str, limit: int = 128) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or any(ch.isspace() for ch in text):
        raise QueueError(f"{label} must be a non-empty token of at most {limit} characters")
    return text


def payload_hash(payload: dict[str, Any]) -> str:
    """Stable hash of a payload without storing the payload itself."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class DurableQueue:
    """Queue protocol over an append-only, totally-ordered event ledger."""

    def __init__(self, ledger):
        for method in ("events", "append"):
            if not hasattr(ledger, method):
                raise QueueError(f"ledger backend must expose {method}()")
        self.ledger = ledger

    # -- replay ---------------------------------------------------------
    def _rows(self, task_id: str | None = None) -> list[dict[str, Any]]:
        rows = [row for row in self.ledger.events(task_id) if row.get("event_type") in EVENT_TYPES]
        return sorted(rows, key=lambda row: row.get("seq", 0))

    @staticmethod
    def _state_from(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        state: dict[str, Any] | None = None
        attempts = 0
        for row in rows:
            payload = row.get("payload", {})
            event_type = row.get("event_type")
            if event_type == ENQUEUED:
                state = {
                    "task_id": row["task_id"],
                    "status": "QUEUED",
                    "attempts": 0,
                    "max_attempts": int(payload.get("max_attempts", 3)),
                    "payload_ref": payload.get("payload_ref"),
                    "payload_hash": payload.get("payload_hash"),
                    "available_at": payload.get("available_at"),
                    "enqueued_at": payload.get("enqueued_at"),
                    "enqueued_seq": row.get("seq"),
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "last_error": None,
                    "last_event_seq": row.get("seq"),
                }
                attempts = 0
                continue
            if state is None:
                continue
            state["last_event_seq"] = row.get("seq")
            if event_type == CLAIMED:
                attempts += 1
                state["status"] = "CLAIMED"
                state["attempts"] = attempts
                state["lease_owner"] = payload.get("owner_id")
                state["lease_expires_at"] = payload.get("lease_expires_at")
            elif event_type == HEARTBEAT:
                if state["status"] == "CLAIMED" and state["lease_owner"] == payload.get("owner_id"):
                    state["lease_expires_at"] = payload.get("lease_expires_at")
            elif event_type == RELEASED:
                state["status"] = "QUEUED"
                state["lease_owner"] = None
                state["lease_expires_at"] = None
                state["available_at"] = payload.get("available_at")
            elif event_type == RECLAIMED:
                state["status"] = "QUEUED"
                state["lease_owner"] = None
                state["lease_expires_at"] = None
                state["last_error"] = payload.get("reason")
            elif event_type == COMPLETED:
                state["status"] = "COMPLETED"
                state["lease_owner"] = None
                state["lease_expires_at"] = None
                state["result_receipt"] = payload.get("receipt")
            elif event_type == FAILED:
                state["status"] = "FAILED"
                state["lease_owner"] = None
                state["lease_expires_at"] = None
                state["last_error"] = payload.get("error")
            elif event_type == CANCELLED:
                state["status"] = "CANCELLED"
                state["lease_owner"] = None
                state["lease_expires_at"] = None
                state["cancel_reason"] = payload.get("reason")
        return state

    def status(self, task_id: str, now: datetime | None = None) -> dict[str, Any] | None:
        instant = now or datetime.now(timezone.utc)
        state = self._state_from(self._rows(task_id))
        if state is None:
            return None
        if state["status"] == "CLAIMED":
            expiry = _parse_instant(state["lease_expires_at"], "lease_expires_at")
            state["lease_active"] = expiry > instant
            state["stale"] = expiry <= instant
        else:
            state["lease_active"] = False
            state["stale"] = False
        return state

    def task_ids(self) -> list[str]:
        seen: list[str] = []
        for row in self._rows():
            if row["task_id"] not in seen:
                seen.append(row["task_id"])
        return seen

    # -- writes ---------------------------------------------------------
    def enqueue(
        self,
        *,
        task_id: str,
        payload_ref: str,
        payload_digest: str,
        max_attempts: int = 3,
        available_at: str | None = None,
        idempotency_key: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        task_id = _require_id(task_id, "task_id")
        payload_ref = _require_id(payload_ref, "payload_ref")
        if not payload_digest or len(str(payload_digest)) < 16:
            raise QueueError("payload_digest must be a stable content hash of the private payload")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 10:
            raise QueueError("max_attempts must be an integer between 1 and 10")
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise QueueError("enqueue time must include a timezone")
        available = available_at or instant.isoformat()
        _parse_instant(available, "available_at")
        payload = {
            "payload_ref": payload_ref,
            "payload_hash": str(payload_digest),
            "max_attempts": max_attempts,
            "available_at": available,
            "enqueued_at": instant.isoformat(),
        }
        event = self.ledger.append(
            task_id=task_id, event_type=ENQUEUED, payload=payload,
            idempotency_key=idempotency_key or f"{task_id}:queue:enqueue",
        )
        return {"enqueued": True, "task_id": task_id, "event": event}

    def claim(
        self,
        *,
        task_id: str,
        owner_id: str,
        lease_seconds: int = 300,
        run_nonce: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        task_id = _require_id(task_id, "task_id")
        owner_id = _require_id(owner_id, "owner_id")
        run_nonce = _require_id(run_nonce, "run_nonce")
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise QueueError("claim time must include a timezone")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or not MIN_LEASE_SECONDS <= lease_seconds <= MAX_LEASE_SECONDS:
            raise QueueError(f"lease_seconds must be between {MIN_LEASE_SECONDS} and {MAX_LEASE_SECONDS}")

        state = self.status(task_id, instant)
        if state is None:
            raise QueueError(f"Unknown queued task: {task_id}")
        if state["status"] in TERMINAL:
            return {"claimed": False, "task_id": task_id, "reason": f"task is {state['status']}"}
        if state["status"] == "CLAIMED" and state["lease_active"]:
            return {"claimed": False, "task_id": task_id, "reason": "active lease held", "owner_id": state["lease_owner"]}
        if state["status"] == "QUEUED" and state.get("available_at"):
            if _parse_instant(state["available_at"], "available_at") > instant:
                return {"claimed": False, "task_id": task_id, "reason": "not yet available"}

        attempt = int(state["attempts"]) + 1
        expiry = (instant + timedelta(seconds=lease_seconds)).isoformat()
        key = f"{task_id}:queue:claim:{attempt}:{owner_id}:{run_nonce}"
        self.ledger.append(
            task_id=task_id, event_type=CLAIMED,
            payload={"owner_id": owner_id, "attempt": attempt, "lease_seconds": lease_seconds,
                     "lease_expires_at": expiry, "claimed_at": instant.isoformat()},
            idempotency_key=key,
        )
        # Re-read: the earliest claim event for this attempt wins.
        winner = None
        for row in self._rows(task_id):
            if row.get("event_type") == CLAIMED and int(row["payload"].get("attempt", 0)) == attempt:
                winner = row["payload"].get("owner_id")
                break
        if winner != owner_id:
            return {"claimed": False, "task_id": task_id, "reason": "lost claim race", "owner_id": winner}
        return {"claimed": True, "task_id": task_id, "owner_id": owner_id, "attempt": attempt,
                "lease_expires_at": expiry}

    def heartbeat(
        self,
        *,
        task_id: str,
        owner_id: str,
        lease_seconds: int = 300,
        run_nonce: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        task_id = _require_id(task_id, "task_id")
        owner_id = _require_id(owner_id, "owner_id")
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise QueueError("heartbeat time must include a timezone")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or not MIN_LEASE_SECONDS <= lease_seconds <= MAX_LEASE_SECONDS:
            raise QueueError(f"lease_seconds must be between {MIN_LEASE_SECONDS} and {MAX_LEASE_SECONDS}")
        state = self.status(task_id, instant)
        if state is None:
            raise QueueError(f"Unknown queued task: {task_id}")
        if state["status"] != "CLAIMED" or state["lease_owner"] != owner_id or not state["lease_active"]:
            return {"renewed": False, "task_id": task_id, "reason": "owner does not hold an active lease"}
        expiry = (instant + timedelta(seconds=lease_seconds)).isoformat()
        self.ledger.append(
            task_id=task_id, event_type=HEARTBEAT,
            payload={"owner_id": owner_id, "lease_expires_at": expiry, "heartbeat_at": instant.isoformat()},
            idempotency_key=f"{task_id}:queue:heartbeat:{owner_id}:{run_nonce}:{instant.isoformat()}",
        )
        after = self.status(task_id, instant)
        return {"renewed": bool(after and after["lease_owner"] == owner_id and after["lease_active"]),
                "task_id": task_id, "lease_expires_at": expiry}

    def complete(
        self,
        *,
        task_id: str,
        owner_id: str,
        receipt: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        instant = now or datetime.now(timezone.utc)
        task_id = _require_id(task_id, "task_id")
        owner_id = _require_id(owner_id, "owner_id")
        state = self.status(task_id, instant)
        if state is None:
            raise QueueError(f"Unknown queued task: {task_id}")
        if state["status"] in TERMINAL:
            return {"completed": False, "task_id": task_id, "reason": f"task is {state['status']}"}
        if state["status"] != "CLAIMED" or state["lease_owner"] != owner_id or not state["lease_active"]:
            return {"completed": False, "task_id": task_id, "reason": "owner does not hold an active lease"}
        self.ledger.append(
            task_id=task_id, event_type=COMPLETED,
            payload={"owner_id": owner_id, "receipt": receipt, "completed_at": instant.isoformat()},
            idempotency_key=f"{task_id}:queue:complete:{state['attempts']}",
        )
        return {"completed": True, "task_id": task_id}

    def fail(
        self,
        *,
        task_id: str,
        owner_id: str,
        error: str,
        backoff_seconds: int = 60,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        instant = now or datetime.now(timezone.utc)
        task_id = _require_id(task_id, "task_id")
        owner_id = _require_id(owner_id, "owner_id")
        if isinstance(backoff_seconds, bool) or not isinstance(backoff_seconds, int) or backoff_seconds < 0:
            raise QueueError("backoff_seconds must be a non-negative integer")
        state = self.status(task_id, instant)
        if state is None:
            raise QueueError(f"Unknown queued task: {task_id}")
        if state["status"] in TERMINAL:
            return {"failed": False, "task_id": task_id, "reason": f"task is {state['status']}"}
        if state["status"] != "CLAIMED" or state["lease_owner"] != owner_id or not state["lease_active"]:
            return {"failed": False, "task_id": task_id, "reason": "owner does not hold an active lease"}
        attempt = int(state["attempts"])
        if attempt >= int(state["max_attempts"]):
            self.ledger.append(
                task_id=task_id, event_type=FAILED,
                payload={"owner_id": owner_id, "error": error, "attempt": attempt, "failed_at": instant.isoformat()},
                idempotency_key=f"{task_id}:queue:failed:{attempt}",
            )
            return {"failed": True, "terminal": True, "task_id": task_id, "attempts": attempt}
        available = (instant + timedelta(seconds=backoff_seconds)).isoformat()
        self.ledger.append(
            task_id=task_id, event_type=RELEASED,
            payload={"owner_id": owner_id, "error": error, "attempt": attempt,
                     "available_at": available, "released_at": instant.isoformat()},
            idempotency_key=f"{task_id}:queue:release-after-failure:{attempt}",
        )
        return {"failed": True, "terminal": False, "task_id": task_id, "attempts": attempt, "available_at": available}

    def cancel(self, *, task_id: str, reason: str, now: datetime | None = None) -> dict[str, Any]:
        instant = now or datetime.now(timezone.utc)
        task_id = _require_id(task_id, "task_id")
        state = self.status(task_id, instant)
        if state is None:
            raise QueueError(f"Unknown queued task: {task_id}")
        if state["status"] in TERMINAL:
            return {"cancelled": False, "task_id": task_id, "reason": f"task is already {state['status']}"}
        self.ledger.append(
            task_id=task_id, event_type=CANCELLED,
            payload={"reason": reason, "cancelled_at": instant.isoformat()},
            idempotency_key=f"{task_id}:queue:cancel",
        )
        return {"cancelled": True, "task_id": task_id}

    def recover_stale(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Reclaim every claimed task whose lease has expired. Idempotent per expiry."""
        instant = now or datetime.now(timezone.utc)
        recovered: list[dict[str, Any]] = []
        for task_id in self.task_ids():
            state = self.status(task_id, instant)
            if not state or state["status"] != "CLAIMED" or not state["stale"]:
                continue
            expiry = state["lease_expires_at"]
            self.ledger.append(
                task_id=task_id, event_type=RECLAIMED,
                payload={"prior_owner_id": state["lease_owner"], "reason": "lease_expired",
                         "expired_at": expiry, "recovered_at": instant.isoformat()},
                idempotency_key=f"{task_id}:queue:reclaim:{expiry}",
            )
            recovered.append({"task_id": task_id, "prior_owner_id": state["lease_owner"], "expired_at": expiry})
        return {"recovered": recovered, "count": len(recovered)}

    # -- reporting ------------------------------------------------------
    def health(self, *, now: datetime | None = None) -> dict[str, Any]:
        instant = now or datetime.now(timezone.utc)
        counts = {"QUEUED": 0, "CLAIMED": 0, "STALE": 0, "COMPLETED": 0, "FAILED": 0, "CANCELLED": 0}
        tasks = []
        for task_id in self.task_ids():
            state = self.status(task_id, instant)
            if not state:
                continue
            bucket = "STALE" if state.get("stale") else state["status"]
            counts[bucket] = counts.get(bucket, 0) + 1
            tasks.append({"task_id": task_id, "status": bucket, "attempts": state["attempts"],
                          "lease_owner": state["lease_owner"], "lease_expires_at": state["lease_expires_at"]})
        return {"counts": counts, "total": len(tasks), "tasks": tasks}

    def reconcile(self, *, expected: dict[str, str], now: datetime | None = None) -> dict[str, Any]:
        """Compare expected task->status against ledger truth; report drift."""
        instant = now or datetime.now(timezone.utc)
        actual = {task_id: (self.status(task_id, instant) or {}).get("status") for task_id in expected}
        drift = {task_id: {"expected": want, "actual": actual.get(task_id)}
                 for task_id, want in expected.items() if actual.get(task_id) != want}
        return {"in_sync": not drift, "drift": drift, "checked": len(expected)}
