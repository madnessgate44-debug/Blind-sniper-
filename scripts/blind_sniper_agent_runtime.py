#!/usr/bin/env python3
"""Connect one native model-agent invocation to the durable Blind Sniper queue.

Task payloads are read from a host-private file and are never copied into the
queue ledger. The ledger stores only a digest, lease events and result digest.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_ledger import GitHubContentsLedger, LedgerError, TaskLedger  # noqa: E402
from blind_sniper_model_worker import AgentSpec, ModelTask, ModelWorker, NativeModelInvoker, ModelWorkerError  # noqa: E402
from blind_sniper_worker import DurableQueue, QueueError  # noqa: E402
from blind_sniper_tool_runtime import NativeToolRuntime  # noqa: E402


class AgentRuntimeError(RuntimeError):
    """Native agent runtime configuration or lifecycle failure."""


def _canonical_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def dispatch_task(
    queue: DurableQueue,
    worker: ModelWorker,
    spec: AgentSpec,
    task: ModelTask,
    *,
    owner_id: str,
    lease_seconds: int = 900,
    receipt_sink: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Enqueue (if new), claim, invoke and commit one correlated model task."""
    if not owner_id.strip():
        raise AgentRuntimeError("owner_id is required")
    if not 1 <= lease_seconds <= 3600:
        raise AgentRuntimeError("lease_seconds must be between 1 and 3600")
    if task.agent_id != spec.agent_id:
        raise AgentRuntimeError("task agent_id must match the supplied AgentSpec")
    envelope = {
        "task_id": task.task_id,
        "agent_id": task.agent_id,
        "objective": task.objective,
        "payload": task.payload,
        "permission_profile": spec.permission_profile,
        "tool_allowlist": list(spec.tool_allowlist),
        "allowed_paths": list(spec.allowed_paths),
        "browser_approval_reference": spec.browser_approval_reference,
    }
    payload_digest = _canonical_digest(envelope)
    current = queue.status(task.task_id)
    if current is None:
        queue.enqueue(
            task_id=task.task_id, kind="native_model_agent",
            payload_digest=payload_digest, max_attempts=3,
        )
    else:
        if current.get("payload_digest") != payload_digest:
            raise AgentRuntimeError("Existing queue task ID is bound to a different payload digest")
        if current.get("status") not in {"PENDING", "RETRY_SCHEDULED"}:
            raise AgentRuntimeError(f"Task is not claimable (status={current.get('status')})")
    claim = queue.claim(owner_id=owner_id, lease_seconds=lease_seconds, task_id=task.task_id)
    if not claim:
        raise AgentRuntimeError("No pending task could be claimed")
    queue.heartbeat(task_id=task.task_id, owner_id=owner_id, lease_seconds=lease_seconds)
    result = worker.run([spec], [replace(task, lease_owner_id=owner_id, lease_seconds=lease_seconds)])
    receipt = result["receipts"][0]
    receipt["queue_attempt"] = claim["attempt"]
    receipt["lease_owner"] = owner_id
    receipt["payload_digest"] = payload_digest
    receipt["queue_task_id"] = task.task_id
    # Persist the full private model result before the queue can become terminal.
    # If the process stops after queue.complete/fail but before notification
    # delivery, the daemon reconciles this receipt against the queue attempt.
    receipt["queue_status"] = "RESULT_READY"
    if receipt_sink is not None:
        receipt_sink(dict(receipt))
    if receipt["status"] == "PASS":
        # A post-invocation heartbeat proves the lease is still held before
        # accepting the result. Completion then atomically consumes that lease.
        queue.heartbeat(task_id=task.task_id, owner_id=owner_id, lease_seconds=lease_seconds)
        queue.complete(
            task_id=task.task_id, owner_id=owner_id,
            result_digest=str(receipt["output_digest"] or _canonical_digest(receipt)),
        )
        receipt["queue_status"] = "COMPLETED"
    else:
        queue.fail(
            task_id=task.task_id, owner_id=owner_id,
            error=str(receipt.get("error", "native model invocation failed"))[:1000],
        )
        receipt["queue_status"] = queue.status(task.task_id)["status"]
    return receipt


def configure_ledger(args) -> Any:
    if not args.github_ledger:
        path = Path(args.ledger).resolve()
        return TaskLedger(path)
    token = os.environ.get(args.github_token_env, "")
    if not token:
        raise AgentRuntimeError(f"Private GitHub ledger requires token in {args.github_token_env}")
    if not (args.github_owner and args.github_repo and args.github_branch):
        raise AgentRuntimeError("--github-ledger requires --github-owner, --github-repo and --github-branch")
    return GitHubContentsLedger(
        owner=args.github_owner, repo=args.github_repo, path=args.github_path,
        branch=args.github_branch, token=token,
    )


def _outside_repository(path: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return resolved
    raise AgentRuntimeError(f"{label} must be outside the public repository workspace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-file", required=True, help="Host-private JSON task envelope; never commit it")
    parser.add_argument("--output", required=True, help="Host-private receipt/output JSON path")
    parser.add_argument("--owner-id", default=f"native-worker-{uuid.uuid4()}")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--max-concurrency", type=int, default=1)
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
    if not 1 <= args.timeout_seconds <= 900:
        print("BLOCKED: timeout must be between 1 and 900 seconds", file=sys.stderr)
        return 2
    try:
        task_path = _outside_repository(Path(args.task_file), "task file")
        output_path = _outside_repository(Path(args.output), "receipt output")
        data = json.loads(task_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise AgentRuntimeError("Task file must contain a JSON object")
        allowed_keys = {"task_id", "agent_id", "objective", "payload", "tool_allowlist", "permission_profile", "allowed_paths", "browser_approval_reference"}
        if set(data) - allowed_keys:
            raise AgentRuntimeError(f"Task file contains unsupported fields: {sorted(set(data) - allowed_keys)}")
        task = ModelTask(
            task_id=str(data.get("task_id", "")),
            agent_id=str(data.get("agent_id", "")),
            objective=str(data.get("objective", "")),
            payload=data.get("payload", {}),
        )
        spec = AgentSpec(
            agent_id=task.agent_id,
            fresh_context=True,
            tool_allowlist=tuple(data.get("tool_allowlist", [])),
            permission_profile=str(data.get("permission_profile", "read_only")),
            allowed_paths=tuple(data.get("allowed_paths", [])),
            browser_approval_reference=str(data.get("browser_approval_reference", "")),
        )
        queue = DurableQueue(configure_ledger(args))
        tool_runtime = NativeToolRuntime(queue)
        invoker = NativeModelInvoker.from_env(tool_runtime=tool_runtime)
        worker = ModelWorker(
            invoker, max_concurrency=args.max_concurrency,
            timeout_seconds=args.timeout_seconds, max_retries=1,
        )
        receipt = dispatch_task(
            queue, worker, spec, task, owner_id=args.owner_id,
            lease_seconds=min(3600, max(60, (args.timeout_seconds * 2) + 60)),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({
            "task_id": receipt["task_id"],
            "agent_id": receipt["agent_id"],
            "run_id": receipt["run_id"],
            "status": receipt["status"],
            "queue_status": receipt["queue_status"],
            "output_digest": receipt.get("output_digest"),
            "receipt_path": str(output_path),
        }, indent=2))
        return 0 if receipt["status"] == "PASS" else 1
    except (AgentRuntimeError, ModelWorkerError, QueueError, LedgerError, OSError, ValueError, TypeError) as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
