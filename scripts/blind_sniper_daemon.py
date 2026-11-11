#!/usr/bin/env python3
"""Persistent native Blind Sniper worker for a private host.

This process polls owner-only task files, recovers stale leases, executes through
the native model/tool runtime, and writes private receipts, health and a local
notification outbox. It is never started by GitHub Actions.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import signal
import stat
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from blind_sniper_agent_runtime import dispatch_task
from blind_sniper_ledger import TaskLedger
from blind_sniper_model_worker import AgentSpec, ModelTask, ModelWorker, NativeModelInvoker
from blind_sniper_tool_runtime import NativeToolRuntime
from blind_sniper_worker import DurableQueue, TERMINAL_STATUSES


TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
MAX_TASK_FILE_BYTES = 2 * 1024 * 1024
ALLOWED_TASK_KEYS = {
    "task_id", "agent_id", "objective", "payload",
}


class DaemonError(RuntimeError):
    """Private worker configuration, task-store or lifecycle failure."""


def validate_host_policy(policy: dict[str, Any]) -> dict[str, Any]:
    profile = policy.get("permission_profile", "read_only")
    tools = tuple(policy.get("tool_allowlist", ()))
    paths = tuple(policy.get("allowed_paths", ()))
    approval = policy.get("browser_approval_reference", "")
    try:
        spec = AgentSpec(
            agent_id="blind-sniper",
            permission_profile=profile,
            tool_allowlist=tools,
            allowed_paths=paths,
            browser_approval_reference=approval,
        )
        NativeToolRuntime.validate_spec(spec)
    except Exception as exc:
        raise DaemonError(f"Host execution policy is invalid ({type(exc).__name__})") from exc
    return {
        "permission_profile": profile,
        "tool_allowlist": tools,
        "allowed_paths": paths,
        "browser_approval_reference": approval,
    }


def load_native_agent_ids(workspace_root: Path) -> frozenset[str]:
    registry_path = workspace_root / "chatgpt-home" / "runtime" / "agents.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        agents = registry["agents"]
        agent_ids = frozenset(item["id"] for item in agents)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DaemonError("Native agent registry is unavailable or invalid") from exc
    if not agent_ids or any(not isinstance(item, str) or not item for item in agent_ids):
        raise DaemonError("Native agent registry contains invalid identities")
    return agent_ids


def host_execution_policy_from_env() -> dict[str, Any]:
    """Load execution privileges exclusively from trusted host configuration."""
    profile = os.environ.get("BLIND_SNIPER_DAEMON_PERMISSION_PROFILE", "read_only").strip()
    tools = tuple(
        item.strip() for item in os.environ.get("BLIND_SNIPER_DAEMON_TOOL_ALLOWLIST", "").split(",")
        if item.strip()
    )
    paths = tuple(
        item.strip() for item in os.environ.get("BLIND_SNIPER_DAEMON_ALLOWED_PATHS", "").split(os.pathsep)
        if item.strip()
    )
    approval = os.environ.get("BLIND_SNIPER_DAEMON_BROWSER_APPROVAL_REFERENCE", "").strip()
    if len(set(tools)) != len(tools) or len(set(paths)) != len(paths):
        raise DaemonError("Host daemon tool and path allowlists must not contain duplicates")
    return validate_host_policy({
        "permission_profile": profile,
        "tool_allowlist": tools,
        "allowed_paths": paths,
        "browser_approval_reference": approval,
    })


def _reject_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise DaemonError(f"Symlink path component is forbidden: {cursor}")


def _ensure_private_dir(path: Path, *, workspace_root: Path) -> Path:
    _reject_symlink_components(path)
    resolved = path.resolve()
    try:
        resolved.relative_to(workspace_root.resolve())
    except ValueError:
        pass
    else:
        raise DaemonError("Private worker state must be outside the public repository workspace")
    if not resolved.exists():
        resolved.mkdir(parents=True, mode=0o700, exist_ok=True)
        os.chmod(resolved, 0o700)
    if not resolved.is_dir():
        raise DaemonError("Private worker state path must be a directory")
    mode = stat.S_IMODE(resolved.stat().st_mode)
    if mode & 0o077:
        raise DaemonError("Private worker directories must have owner-only permissions (0700)")
    return resolved


def _ensure_private_file(path: Path, *, max_bytes: int) -> os.stat_result:
    _reject_symlink_components(path)
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise DaemonError(f"Private task file does not exist: {path.name}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise DaemonError("Private task and receipt paths must be regular files")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise DaemonError("Private task and receipt files must have owner-only permissions (0600)")
    if info.st_size > max_bytes:
        raise DaemonError(f"Private file exceeds the {max_bytes}-byte limit")
    return info


def _atomic_private_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".blind-sniper-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


class PrivateTaskStore:
    """Owner-only task, receipt, health and notification files outside the repo."""

    def __init__(self, state_dir: Path, *, workspace_root: Path = ROOT) -> None:
        self.workspace_root = workspace_root.resolve()
        self.state_dir = _ensure_private_dir(state_dir, workspace_root=self.workspace_root)
        self.task_dir = _ensure_private_dir(self.state_dir / "tasks", workspace_root=self.workspace_root)
        self.receipt_dir = _ensure_private_dir(self.state_dir / "receipts", workspace_root=self.workspace_root)
        self.ledger_dir = _ensure_private_dir(self.state_dir / "ledger", workspace_root=self.workspace_root)
        self.ledger_path = self.ledger_dir / "events.jsonl"
        if self.ledger_path.exists():
            _ensure_private_file(self.ledger_path, max_bytes=1024 * 1024 * 1024)
        else:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(self.ledger_path, flags, 0o600)
            os.close(fd)
        self.health_path = self.state_dir / "health.json"
        self.notification_path = self.state_dir / "notifications.jsonl"

    def task_files(self) -> list[Path]:
        return sorted(self.task_dir.glob("*.json"), key=lambda item: item.name)

    def read_task(self, path: Path) -> dict[str, Any]:
        if path.parent.resolve() != self.task_dir:
            raise DaemonError("Task file must be directly inside the private task directory")
        _ensure_private_file(path, max_bytes=MAX_TASK_FILE_BYTES)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DaemonError(f"Private task JSON is invalid ({type(exc).__name__})") from exc
        if not isinstance(data, dict):
            raise DaemonError("Private task file must contain a JSON object")
        if set(data) - ALLOWED_TASK_KEYS:
            raise DaemonError(f"Private task contains unsupported fields: {sorted(set(data) - ALLOWED_TASK_KEYS)}")
        task_id = data.get("task_id")
        if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
            raise DaemonError("Private task_id is invalid")
        if path.stem != task_id:
            raise DaemonError("Private task filename must be exactly <task_id>.json")
        if not isinstance(data.get("agent_id"), str) or not data["agent_id"].strip():
            raise DaemonError("Private task agent_id is required")
        if not isinstance(data.get("objective"), str) or not data["objective"].strip():
            raise DaemonError("Private task objective is required")
        if not isinstance(data.get("payload", {}), dict):
            raise DaemonError("Private task payload must be an object")
        for key in ("tool_allowlist", "allowed_paths"):
            value = data.get(key, [])
            if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
                raise DaemonError(f"Private task {key} must be an array of non-empty strings")
        approval = data.get("browser_approval_reference", "")
        if not isinstance(approval, str):
            raise DaemonError("browser_approval_reference must be a string")
        return data

    def write_receipt(self, task_id: str, receipt: dict[str, Any]) -> Path:
        if not TASK_ID.fullmatch(task_id):
            raise DaemonError("Receipt task_id is invalid")
        run_id = str(receipt.get("run_id", "no-run"))
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", run_id):
            run_id = "invalid-run"
        path = self.receipt_dir / f"{task_id}__{run_id}.json"
        if path.exists():
            _ensure_private_file(path, max_bytes=MAX_TASK_FILE_BYTES * 2)
            raise DaemonError("Receipt path already exists; refusing overwrite")
        _atomic_private_json(path, receipt)
        return path

    def append_notification(self, event: dict[str, Any]) -> None:
        safe = {
            "event": str(event.get("event", "task.result")),
            "task_id": str(event.get("task_id", "")),
            "run_id": str(event.get("run_id", "")),
            "status": str(event.get("status", "")),
            "result_digest": str(event.get("result_digest", "")),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if not TASK_ID.fullmatch(safe["task_id"]):
            raise DaemonError("Notification task_id is invalid")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", safe["run_id"]):
            raise DaemonError("Notification run_id is invalid")
        if self.notification_path.exists():
            _ensure_private_file(self.notification_path, max_bytes=64 * 1024 * 1024)
        else:
            _reject_symlink_components(self.notification_path)
        flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_NONBLOCK"):
            flags |= os.O_NONBLOCK
        fd = os.open(self.notification_path, flags, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise DaemonError("Notification outbox must be a regular file")
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "a+", encoding="utf-8") as handle:
                fd = -1
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    handle.seek(0)
                    for line in handle:
                        try:
                            existing = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise DaemonError("Notification outbox is corrupt; refusing to append") from exc
                        if (
                            isinstance(existing, dict)
                            and str(existing.get("task_id", "")) == safe["task_id"]
                            and str(existing.get("run_id", "")) == safe["run_id"]
                        ):
                            return
                    handle.seek(0, os.SEEK_END)
                    encoded = json.dumps(safe, sort_keys=True) + "\n"
                    if os.fstat(handle.fileno()).st_size + len(encoded.encode("utf-8")) > 64 * 1024 * 1024:
                        raise DaemonError("Notification outbox exceeds the 64 MiB limit")
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            if fd >= 0:
                os.close(fd)

    def reconcile_notifications(self, queue: DurableQueue) -> int:
        """Rebuild missing metadata-only outbox entries from private durable receipts."""
        known: set[tuple[str, str]] = set()
        if self.notification_path.exists():
            _ensure_private_file(self.notification_path, max_bytes=64 * 1024 * 1024)
            for line in self.notification_path.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DaemonError("Notification outbox is corrupt; refusing to append") from exc
                if isinstance(event, dict):
                    known.add((str(event.get("task_id", "")), str(event.get("run_id", ""))))
        repaired = 0
        for path in sorted(self.receipt_dir.glob("*.json"), key=lambda item: item.name):
            _ensure_private_file(path, max_bytes=MAX_TASK_FILE_BYTES * 2)
            try:
                receipt = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise DaemonError(f"Private receipt is invalid ({type(exc).__name__})") from exc
            if not isinstance(receipt, dict):
                raise DaemonError("Private receipt must contain a JSON object")
            task_id = str(receipt.get("queue_task_id", receipt.get("task_id", "")))
            run_id = str(receipt.get("run_id", ""))
            key = (task_id, run_id)
            if key in known or not TASK_ID.fullmatch(task_id) or not run_id:
                continue
            attempt = receipt.get("queue_attempt")
            current = queue.status(task_id)
            if (
                isinstance(attempt, bool) or not isinstance(attempt, int)
                or not current or current.get("status") not in TERMINAL_STATUSES
                or current.get("attempt") != attempt
            ):
                continue
            status = str(current["status"])
            event_name = "task.completed" if status == "COMPLETED" else "task.failed" if status == "FAILED" else "task.cancelled"
            self.append_notification({
                "event": event_name, "task_id": task_id, "run_id": run_id,
                "status": status, "result_digest": receipt.get("output_digest", ""),
            })
            known.add(key)
            repaired += 1
        return repaired

    def write_health(self, health: dict[str, Any]) -> None:
        _atomic_private_json(self.health_path, health)


class BlindSniperDaemon:
    """Single-process poller; queue leases remain authoritative across restarts."""

    def __init__(
        self,
        *,
        queue: DurableQueue,
        worker: ModelWorker,
        owner_id: str,
        store: PrivateTaskStore,
        lease_seconds: int = 900,
        max_tasks_per_cycle: int = 10,
        host_policy: dict[str, Any] | None = None,
        allowed_agent_ids: frozenset[str] | None = None,
    ) -> None:
        if not owner_id.strip():
            raise DaemonError("owner_id is required")
        if not 60 <= lease_seconds <= 3600:
            raise DaemonError("lease_seconds must be between 60 and 3600")
        if not 1 <= max_tasks_per_cycle <= 100:
            raise DaemonError("max_tasks_per_cycle must be between 1 and 100")
        self.queue = queue
        self.worker = worker
        self.owner_id = owner_id
        self.store = store
        self.lease_seconds = lease_seconds
        self.max_tasks_per_cycle = max_tasks_per_cycle
        self.host_policy = validate_host_policy(host_policy or {})
        self.allowed_agent_ids = allowed_agent_ids
        self._last_success_at: str | None = None

    def _dispatch_task_file(self, data: dict[str, Any]) -> str:
        task_id = data["task_id"]
        current = self.queue.status(task_id)
        if current and (
            current.get("status") in TERMINAL_STATUSES
            or current.get("status") == "CLAIMED"
        ):
            return "SKIPPED"
        spec = AgentSpec(
            agent_id=data["agent_id"],
            tool_allowlist=self.host_policy["tool_allowlist"],
            permission_profile=self.host_policy["permission_profile"],
            allowed_paths=self.host_policy["allowed_paths"],
            browser_approval_reference=self.host_policy["browser_approval_reference"],
        )
        task = ModelTask(
            task_id=task_id,
            agent_id=data["agent_id"],
            objective=data["objective"],
            payload=data.get("payload", {}),
            lease_seconds=self.lease_seconds,
        )
        try:
            receipt = dispatch_task(
                self.queue, self.worker, spec, task,
                owner_id=self.owner_id, lease_seconds=self.lease_seconds,
                receipt_sink=lambda item: self.store.write_receipt(task_id, item),
            )
        except Exception:
            # Another daemon may win the exact-task claim between the status
            # read and dispatch. Treat that race as contention, not a task error.
            current = self.queue.status(task_id)
            if current and (
                current.get("status") in TERMINAL_STATUSES
                or (
                    current.get("status") == "CLAIMED"
                    and current.get("owner_id") != self.owner_id
                )
            ):
                return "SKIPPED"
            raise
        status = receipt.get("queue_status", "")
        if status == "COMPLETED":
            event = "task.completed"
        elif status == "FAILED":
            event = "task.failed"
        else:
            event = "task.retry_scheduled"
        self.store.append_notification({
            "event": event, "task_id": task_id, "run_id": receipt.get("run_id", ""),
            "status": status, "result_digest": receipt.get("output_digest", ""),
        })
        return status

    def run_once(self) -> dict[str, Any]:
        counts = {
            "scanned": 0, "completed": 0, "retry_scheduled": 0, "failed": 0,
            "skipped": 0, "errors": 0, "recovered_stale_leases": 0,
            "notifications_reconciled": 0, "attempted": 0,
        }
        last_error_type = None
        try:
            recovered = self.queue.recover_stale()
            counts["recovered_stale_leases"] = len(recovered.get("recovered", []))
            counts["notifications_reconciled"] = self.store.reconcile_notifications(self.queue)
            files = self.store.task_files()
            counts["scanned"] = len(files)
        except Exception as exc:
            counts["errors"] += 1
            last_error_type = type(exc).__name__
            files = []

        candidates: list[dict[str, Any]] = []
        for path in files:
            try:
                data = self.store.read_task(path)
                if self.allowed_agent_ids is not None and data["agent_id"] not in self.allowed_agent_ids:
                    raise DaemonError("Task agent_id is not registered in the native agent roster")
                current = self.queue.status(data["task_id"])
                if current and (
                    current.get("status") in TERMINAL_STATUSES
                    or current.get("status") == "CLAIMED"
                ):
                    counts["skipped"] += 1
                    continue
                if len(candidates) >= self.max_tasks_per_cycle:
                    break
                candidates.append(data)
            except Exception as exc:
                counts["errors"] += 1
                last_error_type = type(exc).__name__

        counts["attempted"] = len(candidates)
        if candidates:
            worker_count = min(self.worker.max_concurrency, len(candidates))
            with ThreadPoolExecutor(max_workers=worker_count) as pool:
                futures = [pool.submit(self._dispatch_task_file, data) for data in candidates]
                for future in as_completed(futures):
                    try:
                        status = future.result()
                    except Exception as exc:
                        counts["errors"] += 1
                        last_error_type = type(exc).__name__
                        continue
                    if status == "SKIPPED":
                        counts["skipped"] += 1
                    elif status == "COMPLETED":
                        counts["completed"] += 1
                    elif status == "FAILED":
                        counts["failed"] += 1
                    else:
                        counts["retry_scheduled"] += 1

        now = datetime.now(timezone.utc).isoformat()
        if counts["errors"] == 0:
            self._last_success_at = now
        health = {
            "schema_version": 1,
            "status": "DEGRADED" if counts["errors"] else "HEALTHY",
            "owner_id": self.owner_id,
            "updated_at": now,
            "last_success_at": self._last_success_at,
            "last_error_type": last_error_type,
            "counts": counts,
        }
        self.store.write_health(health)
        return health

    def run_forever(self, *, poll_interval: int = 5, stop_event: threading.Event | None = None) -> None:
        if not 1 <= poll_interval <= 300:
            raise DaemonError("poll_interval must be between 1 and 300 seconds")
        stop = stop_event or threading.Event()
        while not stop.is_set():
            self.run_once()
            stop.wait(poll_interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True, help="Owner-only private state directory outside the public repo")
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--poll-interval", type=int, default=5)
    parser.add_argument("--max-tasks-per-cycle", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--max-concurrency", type=int, default=2)
    parser.add_argument("--model-retries", type=int, default=1)
    parser.add_argument("--once", action="store_true", help="Run one poll cycle and exit")
    parser.add_argument("--workspace-root", default=str(ROOT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not 1 <= args.poll_interval <= 300:
            raise DaemonError("poll_interval must be between 1 and 300")
        if not 30 <= args.timeout_seconds <= 900:
            raise DaemonError("timeout_seconds must be between 30 and 900")
        if not 1 <= args.max_concurrency <= 8:
            raise DaemonError("max_concurrency must be between 1 and 8")
        if not 0 <= args.model_retries <= 3:
            raise DaemonError("model_retries must be between 0 and 3")
        workspace_root = Path(args.workspace_root).resolve()
        store = PrivateTaskStore(Path(args.state_dir), workspace_root=workspace_root)
        ledger = TaskLedger(store.ledger_path)
        if store.ledger_path.exists():
            os.chmod(store.ledger_path, 0o600)
        queue = DurableQueue(ledger)
        browser_state_dir = _ensure_private_dir(store.state_dir / "browser", workspace_root=workspace_root)
        tool_runtime = NativeToolRuntime(
            queue, workspace_root=workspace_root,
            command_timeout=min(600, args.timeout_seconds),
            browser_state_dir=browser_state_dir,
        )
        invoker = NativeModelInvoker.from_env(tool_runtime=tool_runtime)
        worker = ModelWorker(
            invoker, max_concurrency=args.max_concurrency,
            timeout_seconds=args.timeout_seconds, max_retries=args.model_retries,
        )
        lease_seconds = min(3600, max(60, (args.timeout_seconds * 2) + 60))
        daemon = BlindSniperDaemon(
            queue=queue, worker=worker, owner_id=args.owner_id, store=store,
            lease_seconds=lease_seconds, max_tasks_per_cycle=args.max_tasks_per_cycle,
            host_policy=host_execution_policy_from_env(),
            allowed_agent_ids=load_native_agent_ids(workspace_root),
        )
        if args.once:
            print(json.dumps(daemon.run_once(), sort_keys=True))
        else:
            print(json.dumps({"status": "STARTED", "owner_id": args.owner_id, "poll_interval": args.poll_interval}, sort_keys=True), flush=True)
            stop = threading.Event()
            def stop_handler(_signum, _frame):
                stop.set()
            signal.signal(signal.SIGTERM, stop_handler)
            signal.signal(signal.SIGINT, stop_handler)
            daemon.run_forever(poll_interval=args.poll_interval, stop_event=stop)
            print(json.dumps({"status": "STOPPED", "owner_id": args.owner_id}, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"BLOCKED: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
