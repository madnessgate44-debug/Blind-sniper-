#!/usr/bin/env python3
"""Independent model-agent worker contract.

This is the R1 execution surface: it invokes *separate* model agents, each with a
distinct agent ID, a fresh context, an explicit tool/permission allowlist, a
correlated task ID, bounded concurrency, a per-attempt timeout, bounded retries
and a redacted receipt per task.

The transport is injected. The real backend is ``OpenHandsCloudInvoker`` over the
V1 API adapter; tests use a deterministic in-process invoker. Selecting an agent
contract is not execution — a receipt exists only after the invoker actually
returns a result.
"""
from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from blind_sniper_redact import redact

AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
PERMISSION_PROFILES = {"read_only", "workspace_write", "restricted"}


class ModelWorkerError(RuntimeError):
    """Model worker contract violation."""


@dataclass(frozen=True)
class AgentSpec:
    """A distinct, independently invoked model agent."""

    agent_id: str
    fresh_context: bool = True
    tool_allowlist: tuple[str, ...] = ()
    permission_profile: str = "read_only"

    def __post_init__(self) -> None:
        if not AGENT_ID.match(self.agent_id):
            raise ModelWorkerError(f"Invalid agent_id: {self.agent_id!r}")
        if self.permission_profile not in PERMISSION_PROFILES:
            raise ModelWorkerError(f"Unknown permission_profile: {self.permission_profile!r}")
        if not self.fresh_context:
            raise ModelWorkerError("Model agents must run with a fresh context")


@dataclass(frozen=True)
class ModelTask:
    task_id: str
    agent_id: str
    objective: str
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not TASK_ID.match(self.task_id):
            raise ModelWorkerError(f"Invalid task_id: {self.task_id!r}")
        if not str(self.objective).strip():
            raise ModelWorkerError("objective is required")


class ModelWorker:
    """Bounded-concurrency dispatcher for independent model agents."""

    def __init__(
        self,
        invoker: Callable[..., dict[str, Any]],
        *,
        max_concurrency: int = 2,
        timeout_seconds: int = 120,
        max_retries: int = 2,
        backoff_seconds: float = 0.0,
    ) -> None:
        if max_concurrency < 1:
            raise ModelWorkerError("max_concurrency must be at least one")
        if not 1 <= timeout_seconds <= 3600:
            raise ModelWorkerError("timeout_seconds must be between 1 and 3600")
        if not 0 <= max_retries <= 5:
            raise ModelWorkerError("max_retries must be between 0 and 5")
        if backoff_seconds < 0:
            raise ModelWorkerError("backoff_seconds must not be negative")
        self.invoker = invoker
        self.max_concurrency = max_concurrency
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._in_flight = 0
        self._lock = threading.Lock()

    def _invoke_once(self, spec: AgentSpec, task: ModelTask) -> dict[str, Any]:
        with self._lock:
            self._in_flight += 1
            if self._in_flight > self.max_concurrency:
                self._in_flight -= 1
                raise ModelWorkerError("Concurrency bound exceeded")
        try:
            # One nested thread gives a hard per-attempt timeout while the outer
            # pool keeps total concurrency bounded.
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    self.invoker, spec=spec, task=task, timeout_seconds=self.timeout_seconds,
                )
                try:
                    return future.result(timeout=self.timeout_seconds)
                except FutureTimeoutError as exc:
                    raise ModelWorkerError("Model invocation timed out") from exc
        finally:
            with self._lock:
                self._in_flight -= 1

    def _run_task(self, spec: AgentSpec, task: ModelTask) -> dict[str, Any]:
        attempts = 0
        last_error = None
        for attempt in range(self.max_retries + 1):
            attempts += 1
            try:
                result = self._invoke_once(spec, task)
            except Exception as exc:  # invoker failure or timeout
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < self.max_retries and self.backoff_seconds:
                    time.sleep(self.backoff_seconds)
                continue
            return {
                "schema_version": "1.0.0",
                "task_id": task.task_id,
                "agent_id": spec.agent_id,
                "status": "PASS",
                "attempts": attempts,
                "permission_profile": spec.permission_profile,
                "tool_allowlist": list(spec.tool_allowlist),
                "fresh_context": spec.fresh_context,
                "conversation_id": result.get("conversation_id") if isinstance(result, dict) else None,
                "output_digest": result.get("output_digest") if isinstance(result, dict) else None,
                "output_excerpt": redact((result or {}).get("output_excerpt", "") if isinstance(result, dict) else ""),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "schema_version": "1.0.0",
            "task_id": task.task_id,
            "agent_id": spec.agent_id,
            "status": "FAIL",
            "attempts": attempts,
            "permission_profile": spec.permission_profile,
            "tool_allowlist": list(spec.tool_allowlist),
            "fresh_context": spec.fresh_context,
            "conversation_id": None,
            "output_digest": None,
            "output_excerpt": "",
            "error": last_error,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    def run(
        self, specs: Iterable[AgentSpec], tasks: Iterable[ModelTask],
    ) -> dict[str, Any]:
        spec_index = {spec.agent_id: spec for spec in specs}
        task_list = list(tasks)
        if not task_list:
            raise ModelWorkerError("At least one task is required")
        seen: set[str] = set()
        for task in task_list:
            if task.task_id in seen:
                raise ModelWorkerError(f"Duplicate task_id: {task.task_id}")
            seen.add(task.task_id)
            if task.agent_id not in spec_index:
                raise ModelWorkerError(f"No agent spec for {task.agent_id}")

        receipts: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as pool:
            futures = {
                pool.submit(self._run_task, spec_index[task.agent_id], task): task
                for task in task_list
            }
            for future in futures:
                receipts.append(future.result())

        by_task = {receipt["task_id"]: receipt for receipt in receipts}
        return {
            "schema_version": "1.0.0",
            "distinct_agents": sorted({task.agent_id for task in task_list}),
            "task_count": len(task_list),
            "passed": sum(1 for r in receipts if r["status"] == "PASS"),
            "failed": sum(1 for r in receipts if r["status"] == "FAIL"),
            "receipts": [by_task[task.task_id] for task in task_list],
        }


class OpenHandsCloudInvoker:
    """Real invoker: create a fresh OpenHands Cloud conversation per task."""

    def __init__(self, client, *, poll_seconds: int = 2, max_poll_seconds: int = 600) -> None:
        self.client = client
        self.poll_seconds = poll_seconds
        self.max_poll_seconds = max_poll_seconds

    def __call__(self, *, spec: AgentSpec, task: ModelTask, timeout_seconds: int) -> dict[str, Any]:
        import hashlib

        start = self.client.start_conversation(
            initial_message=task.objective,
            selected_repository=task.payload.get("repository"),
            idempotency_key=f"{task.task_id}:start",
        )
        start_task_id = start.get("start_task_id")
        if not start_task_id:
            raise ModelWorkerError("OpenHands Cloud did not return a start_task_id")
        polled = self.client.poll_start_task(
            str(start_task_id), timeout_seconds=min(timeout_seconds, self.max_poll_seconds),
            interval_seconds=self.poll_seconds,
        )
        if polled.get("state") not in {"READY"}:
            raise ModelWorkerError(f"OpenHands start task did not become READY: {polled.get('state')}")
        conversation_id = polled.get("app_conversation_id") or start.get("app_conversation_id")
        messages = self.client.get_messages(str(conversation_id)) if conversation_id else {"events": []}
        excerpt = str(messages.get("event_count", 0))
        return {
            "conversation_id": conversation_id,
            "output_digest": hashlib.sha256(str(messages).encode("utf-8")).hexdigest(),
            "output_excerpt": excerpt,
        }
