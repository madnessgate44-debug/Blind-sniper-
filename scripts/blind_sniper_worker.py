#!/usr/bin/env python3
"""Continuous-autonomy worker: one bounded polling pass over the durable queue.

The worker is *invoked*, not resident. Each invocation:

1. Reclaims stale leases (``recover_stale``).
2. Picks the next available queued task and claims it under a lease.
3. Heartbeats while the bounded task runner executes.
4. On failure, applies bounded retry/backoff via ``fail``; on success, completes.
5. Emits a compact health + digest receipt.

This is the executor/data-store logic behind a scheduled or event trigger. The
schedule itself is not activated by this module; the workflow that calls it
stays manual until the executor, private data store and secret prerequisites are
genuinely configured.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_queue as queue_mod  # noqa: E402
from blind_sniper_ledger import LedgerError, TaskLedger  # noqa: E402


class WorkerError(RuntimeError):
    """The worker could not complete a bounded pass."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _available(queue: queue_mod.DurableQueue, task_id: str, instant: datetime) -> bool:
    state = queue.status(task_id, instant)
    if not state or state["status"] != "QUEUED":
        return False
    available_at = state.get("available_at")
    if not available_at:
        return True
    from datetime import datetime as _dt
    return _dt.fromisoformat(str(available_at).replace("Z", "+00:00")) <= instant


def next_available(queue: queue_mod.DurableQueue, instant: datetime) -> str | None:
    for task_id in queue.task_ids():
        if _available(queue, task_id, instant):
            return task_id
    return None


def run_once(
    queue: queue_mod.DurableQueue,
    *,
    owner_id: str,
    run_nonce: str,
    task_runner: Callable[[dict[str, Any]], dict[str, Any]],
    lease_seconds: int = 300,
    backoff_seconds: int = 60,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Execute at most one queued task and return a digest receipt."""
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise WorkerError("worker time must include a timezone")

    recovery = queue.recover_stale(now=instant)
    task_id = next_available(queue, instant)
    if task_id is None:
        return {
            "status": "IDLE",
            "owner_id": owner_id,
            "run_nonce": run_nonce,
            "stale_recovered": recovery["count"],
            "health": queue.health(now=instant),
            "completed_at": _now(),
        }

    claim = queue.claim(task_id=task_id, owner_id=owner_id, lease_seconds=lease_seconds,
                        run_nonce=run_nonce, now=instant)
    if not claim["claimed"]:
        return {
            "status": "CLAIM_LOST",
            "task_id": task_id,
            "reason": claim.get("reason"),
            "stale_recovered": recovery["count"],
            "health": queue.health(now=instant),
            "completed_at": _now(),
        }

    queue.heartbeat(task_id=task_id, owner_id=owner_id, lease_seconds=lease_seconds,
                    run_nonce=run_nonce, now=instant)
    try:
        result = task_runner({"task_id": task_id, "attempt": claim["attempt"]})
        outcome = {"status": "COMPLETED", "task_id": task_id, "attempt": claim["attempt"],
                   "result": result, "stale_recovered": recovery["count"]}
        queue.complete(task_id=task_id, owner_id=owner_id, receipt=result or {}, now=instant)
    except Exception as exc:  # noqa: BLE001 - any runner failure is a bounded failure
        failed = queue.fail(task_id=task_id, owner_id=owner_id, error=f"{type(exc).__name__}: {exc}",
                            backoff_seconds=backoff_seconds, now=instant)
        outcome = {"status": "FAILED", "task_id": task_id, "attempt": claim["attempt"],
                   "terminal": failed["terminal"], "error": f"{type(exc).__name__}: {exc}",
                   "stale_recovered": recovery["count"]}
    outcome["owner_id"] = owner_id
    outcome["run_nonce"] = run_nonce
    outcome["health"] = queue.health(now=instant)
    outcome["completed_at"] = _now()
    return outcome


def health_digest(queue: queue_mod.DurableQueue, *, now: datetime | None = None) -> dict[str, Any]:
    instant = now or datetime.now(timezone.utc)
    health = queue.health(now=instant)
    return {
        "kind": "health_digest",
        "generated_at": instant.isoformat(),
        "counts": health["counts"],
        "total": health["total"],
        "stale": health["counts"].get("STALE", 0),
        "needs_attention": health["counts"].get("STALE", 0) > 0 or health["counts"].get("FAILED", 0) > 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blind Sniper durable-queue worker pass")
    parser.add_argument("--ledger", default=".blind-sniper/state/events.jsonl")
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--run-nonce", required=True)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--sweep-stale", action="store_true",
                        help="Reclaim every claimed task whose lease has expired before reporting.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        queue = queue_mod.DurableQueue(TaskLedger(args.ledger))
        sweep = queue.recover_stale() if args.sweep_stale else {"recovered": [], "count": 0}
        digest = health_digest(queue)
        digest["stale_recovered"] = sweep["count"]
        digest["recovered"] = sweep["recovered"]
        digest["owner_id"] = args.owner_id
        digest["run_nonce"] = args.run_nonce
        digest["note"] = ("Stale-lease sweep and health digest only; task execution is wired "
                          "programmatically through run_once(). No resident process is started.")
        Path(args.output).write_text(json.dumps(digest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(digest, sort_keys=True))
        return 0
    except (WorkerError, queue_mod.QueueError, LedgerError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
