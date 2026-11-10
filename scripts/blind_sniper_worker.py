#!/usr/bin/env python3
"""Durable task queue with claim/lease/heartbeat/cancel/recovery/reconciliation.

The queue is a *protocol* layered on the native append-only ledger, so it
survives independent GitHub Actions runs when the ledger is the private GitHub
Contents CAS store, and works on the local file ledger for tests and single-host
runs. It is not a background daemon and does not claim to be one.

Event types appended (all hash-chained, idempotent and sequence-validated by the
ledger):

``QUEUE_TASK_ENQUEUED`` ``QUEUE_TASK_CLAIMED`` ``QUEUE_TASK_HEARTBEAT``
``QUEUE_TASK_COMPLETED`` ``QUEUE_TASK_FAILED`` ``QUEUE_TASK_CANCELLED``
``QUEUE_TASK_RECOVERED`` ``QUEUE_TASK_RETRY_SCHEDULED``

Every mutating operation is performed through ``ledger.append_guarded`` so the
read-decide-append sequence is atomic under the ledger's file lock (local) or
blob-SHA compare-and-swap (remote). A task payload is never stored here; only a
caller-supplied digest is recorded, so private task content stays out of the
public repository.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from blind_sniper_ledger import LedgerError

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}
CLAIMABLE_STATUSES = {"PENDING"}
ENQUEUED = "QUEUE_TASK_ENQUEUED"
CLAIMED = "QUEUE_TASK_CLAIMED"
HEARTBEAT = "QUEUE_TASK_HEARTBEAT"
COMPLETED = "QUEUE_TASK_COMPLETED"
FAILED = "QUEUE_TASK_FAILED"
CANCELLED = "QUEUE_TASK_CANCELLED"
RECOVERED = "QUEUE_TASK_RECOVERED"
RETRY_SCHEDULED = "QUEUE_TASK_RETRY_SCHEDULED"

MAX_LEASE_SECONDS = 3600


class QueueError(RuntimeError):
    """Durable queue protocol violation."""


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _lease_active(state: dict[str, Any], now: datetime) -> bool:
    if state.get("status") != "CLAIMED":
        return False
    expiry = _parse(state.get("lease_expires_at"))
    return bool(expiry and expiry > now)


def replay_task(rows: list[dict[str, Any]], task_id: str) -> dict[str, Any] | None:
    """Reconstruct one task's queue state by replaying its events in order."""
    state: dict[str, Any] | None = None
    for row in rows:
        if row.get("task_id") != task_id:
            continue
        event_type = row.get("event_type")
        payload = row.get("payload", {})
        if event_type == ENQUEUED:
            state = {
                "task_id": task_id,
                "kind": payload.get("kind"),
                "status": "PENDING",
                "attempt": 0,
                "max_attempts": int(payload.get("max_attempts", 3)),
                "owner_id": None,
                "lease_expires_at": None,
                "heartbeat_at": None,
                "enqueued_at": payload.get("enqueued_at"),
                "payload_digest": payload.get("payload_digest"),
                "result_digest": None,
                "last_error": None,
                "cancel_reason": None,
                "recoveries": 0,
            }
            continue
        if state is None:
            continue
        if event_type == CLAIMED:
            state.update(
                status="CLAIMED", owner_id=payload.get("owner_id"),
                lease_expires_at=payload.get("lease_expires_at"),
                heartbeat_at=payload.get("heartbeat_at"),
                attempt=int(payload.get("attempt", state["attempt"] + 1)),
            )
        elif event_type == HEARTBEAT:
            state.update(
                lease_expires_at=payload.get("lease_expires_at"),
                heartbeat_at=payload.get("heartbeat_at"),
            )
        elif event_type == RECOVERED:
            state.update(
                status="PENDING", owner_id=None, lease_expires_at=None,
                heartbeat_at=None, attempt=int(payload.get("attempt", state["attempt"])),
                recoveries=state["recoveries"] + 1,
            )
        elif event_type == RETRY_SCHEDULED:
            state.update(
                status="PENDING", owner_id=None, lease_expires_at=None,
                heartbeat_at=None, attempt=int(payload.get("attempt", state["attempt"])),
            )
        elif event_type == COMPLETED:
            state.update(status="COMPLETED", owner_id=None, lease_expires_at=None,
                         result_digest=payload.get("result_digest"))
        elif event_type == FAILED:
            state.update(status="FAILED", owner_id=None, lease_expires_at=None,
                         last_error=payload.get("error"))
        elif event_type == CANCELLED:
            state.update(status="CANCELLED", owner_id=None, lease_expires_at=None,
                         cancel_reason=payload.get("reason"))
    return state


class DurableQueue:
    """Claim/lease/heartbeat/cancel/recovery protocol over a native ledger."""

    def __init__(self, ledger: Any, *, max_claim_retries: int = 8) -> None:
        if not hasattr(ledger, "append_guarded") or not hasattr(ledger, "events"):
            raise QueueError("ledger must provide events() and append_guarded()")
        self.ledger = ledger
        self.max_claim_retries = max_claim_retries

    def _append(self, **kwargs: Any) -> dict[str, Any]:
        """append_guarded with LedgerError translated to the queue's own error type."""
        try:
            return self.ledger.append_guarded(**kwargs)
        except LedgerError as exc:
            raise QueueError(str(exc)) from exc

    # -- reads -------------------------------------------------------------
    def _states(self) -> dict[str, dict[str, Any]]:
        rows = self.ledger.events()
        order: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if row.get("event_type") == ENQUEUED and row["task_id"] not in seen:
                seen.add(row["task_id"])
                order.append(row["task_id"])
        return {task_id: replay_task(rows, task_id) for task_id in order}

    def status(self, task_id: str) -> dict[str, Any] | None:
        return replay_task(self.ledger.events(), task_id)

    def list_tasks(self, *, status: str | None = None) -> list[dict[str, Any]]:
        states = self._states()
        values = [state for state in states.values() if state]
        if status is not None:
            values = [state for state in values if state["status"] == status]
        return values

    def health(self, now: datetime | None = None) -> dict[str, Any]:
        instant = now or datetime.now(timezone.utc)
        states = [state for state in self._states().values() if state]
        counts: dict[str, int] = {}
        for state in states:
            counts[state["status"]] = counts.get(state["status"], 0) + 1
        stale = [state["task_id"] for state in states if self._is_stale(state, instant)]
        return {
            "total": len(states),
            "counts": counts,
            "stale_claims": stale,
            "healthy": len(stale) == 0,
        }

    @staticmethod
    def _is_stale(state: dict[str, Any], now: datetime) -> bool:
        if state.get("status") != "CLAIMED":
            return False
        expiry = _parse(state.get("lease_expires_at"))
        return not (expiry and expiry > now)

    # -- writes ------------------------------------------------------------
    def enqueue(
        self,
        *,
        task_id: str,
        kind: str,
        payload_digest: str,
        max_attempts: int = 3,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not str(task_id).strip() or not str(kind).strip():
            raise QueueError("task_id and kind are required")
        if not str(payload_digest).strip():
            raise QueueError("payload_digest is required (store the digest, never the payload)")
        if not isinstance(max_attempts, int) or max_attempts < 1:
            raise QueueError("max_attempts must be a positive integer")
        instant = now or datetime.now(timezone.utc)

        def guard(rows: list[dict[str, Any]], _now: datetime) -> str | None:
            if replay_task(rows, task_id) is not None:
                return f"Task {task_id} is already enqueued"
            return None

        return self._append(
            guard=guard, task_id=task_id, event_type=ENQUEUED,
            payload={
                "kind": kind, "payload_digest": payload_digest,
                "max_attempts": max_attempts, "enqueued_at": instant.isoformat(),
            },
            idempotency_key=f"{task_id}:enqueued",
        )

    def claim(
        self,
        *,
        owner_id: str,
        lease_seconds: int = 300,
        task_id: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Atomically claim the oldest claimable task, or one exact task when task_id is supplied."""
        if not str(owner_id).strip():
            raise QueueError("owner_id is required")
        if task_id is not None and not str(task_id).strip():
            raise QueueError("task_id must be non-empty when supplied")
        if not 1 <= lease_seconds <= MAX_LEASE_SECONDS:
            raise QueueError(f"lease_seconds must be between 1 and {MAX_LEASE_SECONDS}")
        instant = now or datetime.now(timezone.utc)
        for _ in range(self.max_claim_retries):
            states = self._states()
            candidates = [
                state for state in states.values()
                if state and (task_id is None or state["task_id"] == task_id)
                and state["status"] in CLAIMABLE_STATUSES
                and state["attempt"] < state["max_attempts"]
            ]
            if not candidates:
                return None
            candidates.sort(key=lambda state: (state["enqueued_at"] or "", state["task_id"]))
            target = candidates[0]
            attempt = target["attempt"] + 1
            expiry = (instant + timedelta(seconds=lease_seconds)).isoformat()
            payload = {
                "owner_id": owner_id, "attempt": attempt,
                "lease_expires_at": expiry, "heartbeat_at": instant.isoformat(),
            }

            def guard(rows: list[dict[str, Any]], now_locked: datetime, _target=target, _payload=payload) -> str | None:
                state = replay_task(rows, _target["task_id"])
                if state is None:
                    return "Task vanished before claim"
                if state["status"] not in CLAIMABLE_STATUSES:
                    return "Task is no longer claimable"
                if state["attempt"] >= state["max_attempts"]:
                    return "Task has exhausted its attempts"
                if state["attempt"] + 1 != _payload["attempt"]:
                    return "Task attempt changed during claim"
                return None

            try:
                event = self._append(
                    guard=guard, task_id=target["task_id"], event_type=CLAIMED,
                    payload=payload, idempotency_key=f"{target['task_id']}:claim:{attempt}",
                    now=instant,
                )
            except QueueError as exc:  # lost a race against another worker; retry
                if "Task" in str(exc) or "attempt" in str(exc):
                    continue
                raise
            return {
                "task_id": target["task_id"], "owner_id": owner_id,
                "attempt": attempt, "lease_expires_at": expiry, "event": event,
            }
        raise QueueError("Could not claim a task after bounded retries")

    def heartbeat(
        self,
        *,
        task_id: str,
        owner_id: str,
        lease_seconds: int = 300,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not 1 <= lease_seconds <= MAX_LEASE_SECONDS:
            raise QueueError(f"lease_seconds must be between 1 and {MAX_LEASE_SECONDS}")
        instant = now or datetime.now(timezone.utc)
        expiry = (instant + timedelta(seconds=lease_seconds)).isoformat()
        payload = {"owner_id": owner_id, "lease_expires_at": expiry, "heartbeat_at": instant.isoformat()}

        def guard(rows: list[dict[str, Any]], now_locked: datetime) -> str | None:
            state = replay_task(rows, task_id)
            if state is None:
                return f"Unknown task {task_id}"
            if state["status"] != "CLAIMED" or state.get("owner_id") != owner_id:
                return "Heartbeat requires an active lease held by this owner"
            if not _lease_active(state, now_locked):
                return "Cannot heartbeat an expired lease; run recovery first"
            return None

        return self._append(
            guard=guard, task_id=task_id, event_type=HEARTBEAT, payload=payload,
            idempotency_key=f"{task_id}:heartbeat:{payload['heartbeat_at']}", now=instant,
        )

    def complete(
        self, *, task_id: str, owner_id: str, result_digest: str, now: datetime | None = None,
    ) -> dict[str, Any]:
        instant = now or datetime.now(timezone.utc)

        def guard(rows: list[dict[str, Any]], _now: datetime) -> str | None:
            state = replay_task(rows, task_id)
            if state is None:
                return f"Unknown task {task_id}"
            if state["status"] != "CLAIMED" or state.get("owner_id") != owner_id:
                return "Completion requires an active lease held by this owner"
            return None

        return self._append(
            guard=guard, task_id=task_id, event_type=COMPLETED,
            payload={"owner_id": owner_id, "result_digest": result_digest,
                     "completed_at": instant.isoformat()},
            idempotency_key=f"{task_id}:completed", now=instant,
        )

    def fail(
        self, *, task_id: str, owner_id: str, error: str, now: datetime | None = None,
    ) -> dict[str, Any]:
        """Record a failure; requeue for a bounded retry or mark FAILED."""
        instant = now or datetime.now(timezone.utc)

        def guard(rows: list[dict[str, Any]], _now: datetime) -> str | None:
            state = replay_task(rows, task_id)
            if state is None:
                return f"Unknown task {task_id}"
            if state["status"] != "CLAIMED" or state.get("owner_id") != owner_id:
                return "Failure requires an active lease held by this owner"
            return None

        state = self.status(task_id)
        if state is None:
            raise QueueError(f"Unknown task {task_id}")
        if state["attempt"] < state["max_attempts"]:
            return self._append(
                guard=guard, task_id=task_id, event_type=RETRY_SCHEDULED,
                payload={"owner_id": owner_id, "attempt": state["attempt"], "error": error,
                         "failed_at": instant.isoformat()},
                idempotency_key=f"{task_id}:retry:{state['attempt']}", now=instant,
            )
        return self._append(
            guard=guard, task_id=task_id, event_type=FAILED,
            payload={"owner_id": owner_id, "attempt": state["attempt"], "error": error,
                     "failed_at": instant.isoformat()},
            idempotency_key=f"{task_id}:failed", now=instant,
        )

    def cancel(self, *, task_id: str, reason: str, now: datetime | None = None) -> dict[str, Any]:
        instant = now or datetime.now(timezone.utc)

        def guard(rows: list[dict[str, Any]], _now: datetime) -> str | None:
            state = replay_task(rows, task_id)
            if state is None:
                return f"Unknown task {task_id}"
            if state["status"] in TERMINAL_STATUSES:
                return "Task is already terminal"
            return None

        return self._append(
            guard=guard, task_id=task_id, event_type=CANCELLED,
            payload={"reason": reason, "cancelled_at": instant.isoformat()},
            idempotency_key=f"{task_id}:cancelled", now=instant,
        )

    def recover_stale(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Requeue or fail every task whose lease expired without completion."""
        instant = now or datetime.now(timezone.utc)
        states = self._states()
        stale = [state for state in states.values() if state and self._is_stale(state, instant)]
        stale.sort(key=lambda state: (state["enqueued_at"] or "", state["task_id"]))
        recovered: list[str] = []
        failed: list[str] = []
        for state in stale:
            task_id = state["task_id"]
            previous_owner = state.get("owner_id")
            exhausted = state["attempt"] >= state["max_attempts"]

            def guard(rows: list[dict[str, Any]], now_locked: datetime, _tid=task_id) -> str | None:
                current = replay_task(rows, _tid)
                if current is None:
                    return "Task vanished before recovery"
                if current["status"] != "CLAIMED" or not self._is_stale(current, now_locked):
                    return "Task is not a stale claim"
                return None

            if exhausted:
                self._append(
                    guard=guard, task_id=task_id, event_type=FAILED,
                    payload={"owner_id": previous_owner, "attempt": state["attempt"],
                             "error": "lease_lost: attempts exhausted", "recovered_at": instant.isoformat()},
                    idempotency_key=f"{task_id}:failed:lease_lost:{state['attempt']}", now=instant,
                )
                failed.append(task_id)
            else:
                self._append(
                    guard=guard, task_id=task_id, event_type=RECOVERED,
                    payload={"previous_owner": previous_owner, "attempt": state["attempt"],
                             "reason": "STALE_LEASE", "recovered_at": instant.isoformat()},
                    idempotency_key=f"{task_id}:recovered:{state['attempt']}", now=instant,
                )
                recovered.append(task_id)
        return {"recovered": recovered, "failed": failed}

    def reconcile(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Read-only reconciliation report: pending, active, stale and terminal."""
        instant = now or datetime.now(timezone.utc)
        states = [state for state in self._states().values() if state]
        pending = [state["task_id"] for state in states if state["status"] == "PENDING"]
        active = [state["task_id"] for state in states if _lease_active(state, instant)]
        stale = [state["task_id"] for state in states if self._is_stale(state, instant)]
        terminal = [state["task_id"] for state in states if state["status"] in TERMINAL_STATUSES]
        return {
            "schema_version": "1.0.0",
            "at": instant.isoformat(),
            "pending": pending,
            "active_claims": active,
            "stale_claims": stale,
            "terminal": terminal,
            "requires_recovery": bool(stale),
        }
