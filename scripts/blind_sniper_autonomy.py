#!/usr/bin/env python3
"""Safe bounded recovery/health pass for Blind Sniper's durable queue.

This Actions entrypoint is not the native task executor. It may recover stale
leases and emit metadata-only health/digest artifacts, but it MUST NOT claim
pending work or simulate execution. Task execution belongs to the native daemon
on an approved persistent host. No schedule may be enabled until a real
executor, private store, provider and notification delivery route are verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_ledger import GitHubContentsLedger, LedgerError, TaskLedger  # noqa: E402
from blind_sniper_worker import DurableQueue  # noqa: E402


class AutonomyError(RuntimeError):
    """Autonomy runner configuration or execution failure."""


def activation_check(*, github_ledger: bool, ledger_path: str, token_env: str) -> dict[str, Any]:
    """Return whether unattended (scheduled) activation is genuinely safe."""
    data_store = False
    if github_ledger:
        data_store = bool(os.environ.get(token_env, ""))
    else:
        data_store = Path(ledger_path).exists() or Path(ledger_path).parent.exists()
    provider = bool(os.environ.get("BLIND_SNIPER_MODEL_BASE_URL", "").strip() and os.environ.get("BLIND_SNIPER_MODEL_NAME", "").strip())
    # The native daemon is not wired into this ephemeral Actions entrypoint.
    executor = False
    prerequisites = {
        "data_store_configured": data_store,
        "native_model_provider_configured": provider,
        "executor_configured": executor,
        # A metadata outbox is not a delivery route. No native delivery adapter exists here.
        "notification_route_configured": False,
    }
    return {
        "activation_allowed": all(prerequisites.values()),
        "prerequisites": prerequisites,
        "note": "A schedule may only be enabled when every prerequisite is true.",
    }


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def configure_ledger(args) -> Any:
    if not args.github_ledger:
        return TaskLedger(args.ledger)
    token = os.environ.get(args.github_token_env, "")
    if not token:
        raise AutonomyError(f"GitHub ledger requires token in {args.github_token_env}")
    if not (args.github_owner and args.github_repo and args.github_branch):
        raise AutonomyError("--github-ledger requires --github-owner, --github-repo and --github-branch")
    return GitHubContentsLedger(
        owner=args.github_owner, repo=args.github_repo, path=args.github_path,
        branch=args.github_branch, token=token,
    )


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_once(
    queue: DurableQueue, *, owner_id: str, max_tasks: int, output_dir: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One bounded pass: recover stale leases and report without claiming tasks."""
    if not 1 <= max_tasks <= 100:
        raise AutonomyError("max_tasks must be between 1 and 100")
    instant = now or datetime.now(timezone.utc)
    recovery = queue.recover_stale(now=instant)
    raw_health = queue.health(now=instant)
    raw_reconciliation = queue.reconcile(now=instant)
    # This output is uploaded as a GitHub Actions artifact in a public repository.
    # Publish aggregate counts only; never expose private task IDs or payload metadata.
    health = {
        "total": raw_health["total"],
        "counts": raw_health["counts"],
        "stale_count": len(raw_health["stale_claims"]),
        "healthy": raw_health["healthy"],
    }
    reconciliation = {
        "pending_count": len(raw_reconciliation["pending"]),
        "active_claim_count": len(raw_reconciliation["active_claims"]),
        "stale_claim_count": len(raw_reconciliation["stale_claims"]),
        "terminal_count": len(raw_reconciliation["terminal"]),
        "requires_recovery": raw_reconciliation["requires_recovery"],
    }
    digest = {
        "schema_version": "1.0.0",
        "kind": "autonomy_digest",
        "at": instant.isoformat(),
        "execution_status": "BLOCKED_NO_EXECUTOR",
        "execution_note": "This ephemeral runner has no native task executor wired; pending tasks were not claimed.",
        "max_tasks_limit": max_tasks,
        "tasks_started": 0,
        "recovered_stale_count": len(recovery["recovered"]),
        "failed_exhausted_count": len(recovery["failed"]),
        "drained": [],
        "pending_count": reconciliation["pending_count"],
        "health": health,
        "reconciliation": reconciliation,
        "notification_delivery_status": "NOT_CONFIGURED",
        "digest_sha256": _digest(json.dumps(health, sort_keys=True)),
    }
    write_json(output_dir / "autonomy-digest.json", digest)
    write_json(output_dir / "autonomy-health.json", health)
    return digest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--max-tasks", type=int, default=5)
    parser.add_argument("--output-dir", default="artifacts/blind-sniper-autonomy")
    parser.add_argument("--check-activation-only", action="store_true")
    parser.add_argument("--ledger", default=".blind-sniper/state/events.jsonl")
    parser.add_argument("--github-ledger", action="store_true")
    parser.add_argument("--github-owner")
    parser.add_argument("--github-repo")
    parser.add_argument("--github-branch")
    parser.add_argument("--github-path", default="blind-sniper-continuity/QUEUE.jsonl")
    parser.add_argument("--github-token-env", default="GITHUB_TOKEN")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_tasks < 1 or args.max_tasks > 100:
        print("BLOCKED: --max-tasks must be between 1 and 100", file=sys.stderr)
        return 2
    check = activation_check(
        github_ledger=args.github_ledger, ledger_path=args.ledger,
        token_env=args.github_token_env,
    )
    if args.check_activation_only:
        print(json.dumps(check, indent=2, sort_keys=True))
        return 0 if check["activation_allowed"] else 1
    if not check["activation_allowed"]:
        print(
            "BLOCKED: unattended activation prerequisites are not configured: "
            f"{check['prerequisites']}",
            file=sys.stderr,
        )
        return 2
    try:
        ledger = configure_ledger(args)
        digest = run_once(
            DurableQueue(ledger), owner_id=args.owner_id,
            max_tasks=args.max_tasks, output_dir=Path(args.output_dir).resolve(),
        )
    except (AutonomyError, LedgerError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(digest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
