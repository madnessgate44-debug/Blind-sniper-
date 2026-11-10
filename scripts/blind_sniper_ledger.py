#!/usr/bin/env python3
"""Native append-only task event ledger for Blind Sniper.

This is a durable local-workspace store, not a claim of cross-runner storage.
Cross-session/cloud durability requires a persistent workspace or a future
GitHub-backed compare-and-swap adapter.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from typing import Any


class LedgerError(ValueError):
    """Invalid, corrupt, or conflicting ledger operation."""


MAX_LEDGER_BYTES = 512 * 1024


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _authoritative_task_state(rows: list[dict[str, Any]], task_id: str) -> dict[str, Any] | None:
    """Reconstruct the current task state core by replaying this task's events.

    Mirrors ``runtime.recover_task_state`` so that lease guards read the
    authoritative status/implementer from compact state snapshots and deltas,
    not merely from a legacy full-snapshot ``state`` field that compact writes
    never update. Legacy full snapshots are still accepted for recovery.
    """
    core: dict[str, Any] | None = None
    for row in rows:
        if row.get("task_id") != task_id:
            continue
        payload = row.get("payload", {})
        legacy = payload.get("state")
        if isinstance(legacy, dict):
            core = {key: value for key, value in legacy.items() if key != "events"}
            continue
        snapshot = payload.get("state_snapshot")
        if isinstance(snapshot, dict):
            if _digest(snapshot) != payload.get("state_hash"):
                raise LedgerError("Task state snapshot hash mismatch")
            core = snapshot
        elif isinstance(payload.get("state_delta"), dict):
            if core is None or _digest(core) != payload.get("previous_state_hash"):
                raise LedgerError("Task state delta predecessor hash mismatch")
            delta = payload["state_delta"]
            core = dict(core)
            core.update(delta.get("set", {}))
            for key in delta.get("remove", []):
                core.pop(key, None)
            if _digest(core) != payload.get("state_hash"):
                raise LedgerError("Task state delta hash mismatch")
    return core


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

    def _append_locked(
        self,
        handle,
        rows: list[dict[str, Any]],
        *,
        task_id: str,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> tuple[dict[str, Any], bool]:
        for row in rows:
            if row["idempotency_key"] == idempotency_key:
                if row["task_id"] != task_id or row["event_type"] != event_type or row["payload"] != payload:
                    raise LedgerError("idempotency key already used for different event content")
                return row, False
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
        line = (json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        handle.seek(0, os.SEEK_END)
        if handle.tell() + len(line) > MAX_LEDGER_BYTES:
            raise LedgerError(f"Ledger append refused: total size would exceed {MAX_LEDGER_BYTES} bytes")
        handle.write(line.decode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
        return event, True

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
                event, _ = self._append_locked(
                    handle, rows, task_id=task_id, event_type=event_type,
                    payload=payload, idempotency_key=idempotency_key,
                )
                return event
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _active_lease(rows: list[dict[str, Any]], task_id: str, now: datetime):
        lease = None
        for row in rows:
            if row.get("task_id") != task_id:
                continue
            if row.get("event_type") in ("TASK_LEASE_CLAIMED", "TASK_LEASE_RENEWED"):
                lease = row.get("payload")
            elif row.get("event_type") == "TASK_LEASE_RELEASED":
                lease = None
        if not lease:
            return None
        try:
            expiry = datetime.fromisoformat(str(lease["lease_expires_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError) as exc:
            raise LedgerError("Malformed task lease event") from exc
        if expiry.tzinfo is None:
            raise LedgerError("Task lease expiry must include a timezone")
        return lease if expiry > now else None

    def lease_status(self, task_id: str, now: datetime | None = None):
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise LedgerError("lease status time must include a timezone")
        rows = self.events(task_id)
        lease = self._active_lease(rows, task_id, instant)
        if lease is None:
            return None
        return {
            "task_id": task_id,
            "owner_id": lease["owner_id"],
            "lease_expires_at": lease["lease_expires_at"],
        }

    def reserve_browser_action_if_lease(
        self,
        *,
        task_id: str,
        owner_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        min_remaining_seconds: int,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Atomically validate EXECUTING state/lease and reserve one browser step."""
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise LedgerError("browser reservation time must include a timezone")
        if not task_id.strip() or not owner_id.strip() or not idempotency_key.strip():
            raise LedgerError("task_id, owner_id and idempotency_key are required")
        if isinstance(min_remaining_seconds, bool) or not isinstance(min_remaining_seconds, int) or min_remaining_seconds < 1:
            raise LedgerError("min_remaining_seconds must be a positive integer")
        if not isinstance(payload, dict):
            raise LedgerError("browser reservation payload must be an object")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                rows = self._read_unlocked()
                state = _authoritative_task_state(rows, task_id)
                if not isinstance(state, dict) or state.get("status") != "EXECUTING":
                    raise LedgerError("Browser reservation requires authoritative task status EXECUTING")
                if state.get("implementer_id") != owner_id:
                    raise LedgerError("Browser reservation owner does not match executing implementer")
                active = self._active_lease(rows, task_id, instant)
                if not active or active.get("owner_id") != owner_id:
                    raise LedgerError("Browser reservation requires an active lease held by this owner")
                expiry = datetime.fromisoformat(str(active["lease_expires_at"]).replace("Z", "+00:00"))
                if (expiry - instant).total_seconds() <= min_remaining_seconds:
                    raise LedgerError("Task lease has insufficient remaining time for browser action")
                if any(row.get("idempotency_key") == idempotency_key for row in rows):
                    raise LedgerError("Browser step already reserved; duplicate or interrupted replay is forbidden")
                event, created = self._append_locked(
                    handle, rows, task_id=task_id, event_type="BROWSER_ACTION_STARTED",
                    payload=payload, idempotency_key=idempotency_key,
                )
                if not created:
                    raise LedgerError("Browser step reservation was not newly created")
                return {"reserved": True, "event": event}
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def claim_task(
        self,
        *,
        task_id: str,
        owner_id: str,
        lease_seconds: int,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise LedgerError("claim time must include a timezone")
        if not task_id.strip() or not owner_id.strip() or not idempotency_key.strip():
            raise LedgerError("task_id, owner_id and idempotency_key are required")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or lease_seconds < 1 or lease_seconds > 3600:
            raise LedgerError("lease_seconds must be between 1 and 3600")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                rows = self._read_unlocked()
                latest_status = None
                for row in rows:
                    if row.get("task_id") != task_id:
                        continue
                    payload = row.get("payload", {})
                    legacy = payload.get("state")
                    snapshot = payload.get("state_snapshot")
                    delta = payload.get("state_delta", {})
                    if isinstance(legacy, dict):
                        latest_status = legacy.get("status", latest_status)
                    elif isinstance(snapshot, dict):
                        latest_status = snapshot.get("status", latest_status)
                    if isinstance(delta, dict) and "status" in delta.get("set", {}):
                        latest_status = delta["set"]["status"]
                if latest_status in ("CLOSED", "CANCELLED"):
                    raise LedgerError("A terminal task cannot be claimed")
                existing = next((row for row in rows if row["idempotency_key"] == idempotency_key), None)
                if existing:
                    if existing["task_id"] != task_id or existing["event_type"] not in ("TASK_LEASE_CLAIMED", "TASK_LEASE_RENEWED") or existing["payload"].get("owner_id") != owner_id:
                        raise LedgerError("idempotency key already used for different lease content")
                    active = self._active_lease(rows, task_id, instant)
                    return {
                        "claimed": bool(active and active.get("owner_id") == owner_id),
                        "owner_id": active.get("owner_id") if active else None,
                        "lease_expires_at": active.get("lease_expires_at") if active else None,
                        "event": existing,
                        "event_created": False,
                    }
                active = self._active_lease(rows, task_id, instant)
                if active and active.get("owner_id") != owner_id:
                    return {
                        "claimed": False,
                        "owner_id": active["owner_id"],
                        "lease_expires_at": active["lease_expires_at"],
                        "event": None,
                        "event_created": False,
                    }
                event_type = "TASK_LEASE_RENEWED" if active else "TASK_LEASE_CLAIMED"
                expiry = (instant + timedelta(seconds=lease_seconds)).isoformat()
                payload = {
                    "owner_id": owner_id,
                    "lease_seconds": lease_seconds,
                    "lease_expires_at": expiry,
                }
                event, created = self._append_locked(
                    handle, rows, task_id=task_id, event_type=event_type,
                    payload=payload, idempotency_key=idempotency_key,
                )
                return {
                    "claimed": True,
                    "owner_id": owner_id,
                    "lease_expires_at": expiry,
                    "event": event,
                    "event_created": created,
                }
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def release_task(
        self,
        *,
        task_id: str,
        owner_id: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise LedgerError("release time must include a timezone")
        if not task_id.strip() or not owner_id.strip() or not idempotency_key.strip():
            raise LedgerError("task_id, owner_id and idempotency_key are required")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                rows = self._read_unlocked()
                existing = next((row for row in rows if row["idempotency_key"] == idempotency_key), None)
                if existing:
                    if existing["task_id"] != task_id or existing["event_type"] != "TASK_LEASE_RELEASED" or existing["payload"].get("owner_id") != owner_id:
                        raise LedgerError("idempotency key already used for different release content")
                    return {"released": True, "event": existing, "event_created": False}
                active = self._active_lease(rows, task_id, instant)
                if not active or active.get("owner_id") != owner_id:
                    return {"released": False, "event": None, "event_created": False}
                payload = {"owner_id": owner_id, "released_at": instant.isoformat()}
                event, created = self._append_locked(
                    handle, rows, task_id=task_id, event_type="TASK_LEASE_RELEASED",
                    payload=payload, idempotency_key=idempotency_key,
                )
                return {"released": True, "event": event, "event_created": created}
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def append_transition_if_lease(
        self,
        *,
        task_id: str,
        owner_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Atomically verify lease ownership and append an EXECUTING transition receipt."""
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise LedgerError("transition time must include a timezone")
        if not task_id.strip() or not owner_id.strip() or not idempotency_key.strip():
            raise LedgerError("task_id, owner_id and idempotency_key are required")
        if not isinstance(payload, dict):
            raise LedgerError("payload must be an object")
        snapshot = payload.get("state")
        guard = payload.get("lease_guard", {})
        snapshot_task = snapshot.get("task_id") if isinstance(snapshot, dict) else guard.get("task_id")
        snapshot_status = snapshot.get("status") if isinstance(snapshot, dict) else guard.get("status")
        snapshot_owner = snapshot.get("implementer_id") if isinstance(snapshot, dict) else guard.get("implementer_id")
        allowed_statuses = {"EXECUTING", "VERIFYING", "REVIEWING", "CLOSED", "BLOCKED", "FAILED", "OWNER-DECISION", "CANCELLED"}
        if snapshot_task != task_id or snapshot_status not in allowed_statuses or snapshot_owner != owner_id:
            raise LedgerError("Lease-gated transition requires an active lease and matching post-EXECUTING snapshot implementer")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                rows = self._read_unlocked()
                active = self._active_lease(rows, task_id, instant)
                if not active or active.get("owner_id") != owner_id:
                    raise LedgerError("Execution transition requires an active lease held by this owner")
                event, _ = self._append_locked(
                    handle, rows, task_id=task_id, event_type="TASK_TRANSITIONED",
                    payload=payload, idempotency_key=idempotency_key,
                )
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


class GitHubLedgerError(LedgerError):
    """GitHub Contents API ledger failure or exhausted concurrency retries."""


class GitHubContentsLedger:
    """Optional append-only ledger adapter using GitHub Contents API SHA compare-and-swap.

    Each append creates a commit containing the complete validated JSONL ledger.
    This is suitable for small control-plane state files, not large transcripts.
    """

    def __init__(
        self,
        *,
        owner: str,
        repo: str,
        path: str,
        branch: str,
        token: str,
        transport=None,
        max_retries: int = 3,
    ):
        if not all(value.strip() for value in (owner, repo, path, branch, token)):
            raise GitHubLedgerError("owner, repo, path, branch and token are required")
        if max_retries < 1:
            raise GitHubLedgerError("max_retries must be at least one")
        self.owner = owner
        self.repo = repo
        self.path = path
        self.branch = branch
        self.token = token
        self.transport = transport or self._urlopen_transport
        self.max_retries = max_retries
        self.api_url = (
            f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}"
            f"/contents/{quote(path, safe='/')}"
        )

    @staticmethod
    def _urlopen_transport(method: str, url: str, headers: dict, body: bytes | None = None):
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=20) as response:
                return response.status, response.read(), dict(response.headers.items())
        except HTTPError as exc:
            return exc.code, exc.read(), dict(exc.headers.items())
        except URLError as exc:
            raise GitHubLedgerError(f"GitHub Contents API transport failed: {exc.reason}") from exc

    def _request(self, method: str, url: str, body: bytes | None = None):
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Blind-Sniper-Native-Ledger",
        }
        self._server_time = None
        response = self.transport(method, url, headers, body)
        if len(response) == 3:
            status, raw, response_headers = response
            date_value = next((value for key, value in response_headers.items() if key.lower() == "date"), None)
            if date_value:
                try:
                    parsed = parsedate_to_datetime(date_value)
                    self._server_time = parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise GitHubLedgerError("GitHub response Date header is invalid") from exc
        else:
            status, raw = response
        return status, raw

    def _server_now(self) -> datetime:
        if self._server_time is None:
            raise GitHubLedgerError("GitHub response Date header is required for lease expiry")
        return self._server_time

    def _assert_private_repository(self) -> None:
        repo_url = f"https://api.github.com/repos/{quote(self.owner)}/{quote(self.repo)}"
        status, raw = self._request("GET", repo_url)
        if status != 200:
            raise GitHubLedgerError(f"GitHub ledger repository metadata check failed with HTTP {status}")
        try:
            metadata = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubLedgerError("GitHub ledger repository metadata is malformed") from exc
        if metadata.get("private") is not True:
            raise GitHubLedgerError("GitHub ledger refuses to write or read task state in a public repository")

    def _read_remote(self) -> tuple[bytes, str | None]:
        self._assert_private_repository()
        status, raw = self._request("GET", f"{self.api_url}?ref={quote(self.branch)}")
        if status == 404:
            return b"", None
        if status != 200:
            raise GitHubLedgerError(f"GitHub ledger read failed with HTTP {status}")
        try:
            response = json.loads(raw.decode("utf-8"))
            if response.get("encoding") != "base64":
                raise GitHubLedgerError("GitHub ledger response is not base64 encoded")
            content = base64.b64decode(response["content"], validate=False)
            if len(content) > MAX_LEDGER_BYTES:
                raise GitHubLedgerError(f"Remote ledger exceeds the {MAX_LEDGER_BYTES}-byte safety limit")
            sha = str(response["sha"])
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, GitHubLedgerError):
                raise
            raise GitHubLedgerError("GitHub ledger response is malformed") from exc
        return content, sha

    def events(self, task_id: str | None = None) -> list[dict[str, Any]]:
        remote_content, _ = self._read_remote()
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "events.jsonl"
            local_path.write_bytes(remote_content)
            try:
                return TaskLedger(local_path).events(task_id)
            except LedgerError as exc:
                raise GitHubLedgerError(f"Remote ledger integrity check failed: {exc}") from exc

    def task_history(self, task_id: str) -> dict[str, Any]:
        rows = self.events(task_id)
        if not rows:
            raise GitHubLedgerError(f"Unknown task_id: {task_id}")
        return {
            "task_id": task_id,
            "event_count": len(rows),
            "last_event": rows[-1],
            "events": rows,
        }

    def _write_remote_content(
        self,
        *,
        content: bytes,
        remote_sha: str | None,
        task_id: str,
        event_type: str,
    ) -> str | None:
        put_payload = {
            "message": f"blind-sniper: append task event {task_id}/{event_type}",
            "content": base64.b64encode(content).decode("ascii"),
            "branch": self.branch,
        }
        if remote_sha:
            put_payload["sha"] = remote_sha
        status, raw = self._request(
            "PUT", self.api_url,
            json.dumps(put_payload, separators=(",", ":")).encode("utf-8"),
        )
        if status in (409, 422):
            return None
        if status not in (200, 201):
            raise GitHubLedgerError(f"GitHub ledger write failed with HTTP {status}")
        try:
            response = json.loads(raw.decode("utf-8"))
            return response["commit"]["sha"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise GitHubLedgerError("GitHub ledger write receipt is malformed") from exc

    def claim_task(
        self,
        *,
        task_id: str,
        owner_id: str,
        lease_seconds: int,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        for _ in range(self.max_retries):
            remote_content, remote_sha = self._read_remote()
            with tempfile.TemporaryDirectory() as tmp:
                local_path = Path(tmp) / "events.jsonl"
                local_path.write_bytes(remote_content)
                local = TaskLedger(local_path)
                try:
                    result = local.claim_task(
                        task_id=task_id, owner_id=owner_id, lease_seconds=lease_seconds,
                        idempotency_key=idempotency_key, now=self._server_now(),
                    )
                except LedgerError as exc:
                    raise GitHubLedgerError(str(exc)) from exc
                if not result["claimed"] or not result["event_created"]:
                    return result
                updated_content = local_path.read_bytes()
            commit_sha = self._write_remote_content(
                content=updated_content, remote_sha=remote_sha,
                task_id=task_id, event_type=result["event"]["event_type"],
            )
            if commit_sha is None:
                continue
            result["event"] = {**result["event"], "commit_sha": commit_sha}
            return result
        raise GitHubLedgerError(f"GitHub lease claim CAS failed after {self.max_retries} attempts")

    def release_task(
        self,
        *,
        task_id: str,
        owner_id: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        for _ in range(self.max_retries):
            remote_content, remote_sha = self._read_remote()
            with tempfile.TemporaryDirectory() as tmp:
                local_path = Path(tmp) / "events.jsonl"
                local_path.write_bytes(remote_content)
                local = TaskLedger(local_path)
                try:
                    result = local.release_task(
                        task_id=task_id, owner_id=owner_id,
                        idempotency_key=idempotency_key, now=self._server_now(),
                    )
                except LedgerError as exc:
                    raise GitHubLedgerError(str(exc)) from exc
                if not result["released"] or not result["event_created"]:
                    return result
                updated_content = local_path.read_bytes()
            commit_sha = self._write_remote_content(
                content=updated_content, remote_sha=remote_sha,
                task_id=task_id, event_type="TASK_LEASE_RELEASED",
            )
            if commit_sha is None:
                continue
            result["event"] = {**result["event"], "commit_sha": commit_sha}
            return result
        raise GitHubLedgerError(f"GitHub lease release CAS failed after {self.max_retries} attempts")

    def lease_status(self, task_id: str, now: datetime | None = None):
        remote_content, _ = self._read_remote()
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "events.jsonl"
            local_path.write_bytes(remote_content)
            try:
                return TaskLedger(local_path).lease_status(task_id, self._server_now())
            except LedgerError as exc:
                raise GitHubLedgerError(f"Remote lease history is invalid: {exc}") from exc

    def reserve_browser_action_if_lease(
        self,
        *,
        task_id: str,
        owner_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        min_remaining_seconds: int,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Reserve a browser step using GitHub Contents SHA-CAS and native lease checks."""
        for _ in range(self.max_retries):
            remote_content, remote_sha = self._read_remote()
            with tempfile.TemporaryDirectory() as tmp:
                local_path = Path(tmp) / "events.jsonl"
                local_path.write_bytes(remote_content)
                local = TaskLedger(local_path)
                try:
                    result = local.reserve_browser_action_if_lease(
                        task_id=task_id, owner_id=owner_id, payload=payload,
                        idempotency_key=idempotency_key,
                        min_remaining_seconds=min_remaining_seconds, now=now,
                    )
                except LedgerError as exc:
                    raise GitHubLedgerError(str(exc)) from exc
                updated_content = local_path.read_bytes()
            commit_sha = self._write_remote_content(
                content=updated_content, remote_sha=remote_sha,
                task_id=task_id, event_type="BROWSER_ACTION_STARTED",
            )
            if commit_sha is None:
                continue
            return {"reserved": True, "event": {**result["event"], "commit_sha": commit_sha}}
        raise GitHubLedgerError(f"GitHub browser reservation CAS failed after {self.max_retries} attempts")

    def append_transition_if_lease(
        self,
        *,
        task_id: str,
        owner_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        for _ in range(self.max_retries):
            remote_content, remote_sha = self._read_remote()
            with tempfile.TemporaryDirectory() as tmp:
                local_path = Path(tmp) / "events.jsonl"
                local_path.write_bytes(remote_content)
                local = TaskLedger(local_path)
                try:
                    event = local.append_transition_if_lease(
                        task_id=task_id, owner_id=owner_id, payload=payload,
                        idempotency_key=idempotency_key, now=self._server_now(),
                    )
                except LedgerError as exc:
                    raise GitHubLedgerError(str(exc)) from exc
                updated_content = local_path.read_bytes()
            commit_sha = self._write_remote_content(
                content=updated_content, remote_sha=remote_sha,
                task_id=task_id, event_type="TASK_TRANSITIONED",
            )
            if commit_sha is None:
                continue
            return {**event, "commit_sha": commit_sha}
        raise GitHubLedgerError(f"GitHub execution-transition CAS failed after {self.max_retries} attempts")

    def append(
        self,
        *,
        task_id: str,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        for attempt in range(1, self.max_retries + 1):
            remote_content, remote_sha = self._read_remote()
            with tempfile.TemporaryDirectory() as tmp:
                local_path = Path(tmp) / "events.jsonl"
                local_path.write_bytes(remote_content)
                local = TaskLedger(local_path)
                try:
                    rows = local.events()  # validates the entire remote hash chain
                except LedgerError as exc:
                    raise GitHubLedgerError(f"Remote ledger integrity check failed: {exc}") from exc
                existing = next((row for row in rows if row.get("idempotency_key") == idempotency_key), None)
                try:
                    event = local.append(
                        task_id=task_id,
                        event_type=event_type,
                        payload=payload,
                        idempotency_key=idempotency_key,
                    )
                except LedgerError as exc:
                    raise GitHubLedgerError(str(exc)) from exc
                if existing is not None:
                    return {**event, "already_present": True, "commit_sha": None}
                updated_content = local_path.read_bytes()
            put_payload = {
                "message": f"blind-sniper: append task event {task_id}/{event_type}",
                "content": base64.b64encode(updated_content).decode("ascii"),
                "branch": self.branch,
            }
            if remote_sha:
                put_payload["sha"] = remote_sha
            status, raw = self._request(
                "PUT", self.api_url,
                json.dumps(put_payload, separators=(",", ":")).encode("utf-8"),
            )
            if status in (409, 422):
                # Another writer changed the blob SHA. Reload and re-append against
                # the latest hash-chain head rather than overwriting that writer.
                continue
            if status not in (200, 201):
                raise GitHubLedgerError(f"GitHub ledger write failed with HTTP {status}")
            try:
                response = json.loads(raw.decode("utf-8"))
                commit_sha = response["commit"]["sha"]
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
                raise GitHubLedgerError("GitHub ledger write receipt is malformed") from exc
            return {**event, "already_present": False, "commit_sha": commit_sha}
        raise GitHubLedgerError(
            f"GitHub ledger compare-and-swap failed after {self.max_retries} attempts"
        )


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
