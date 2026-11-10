#!/usr/bin/env python3
"""Bounded, independently-invoked model worker.

This module makes *real* separate model invocations, each with its own agent ID
and fresh message context, rather than declaring an agent contract. It is the
execution layer the runtime planner previously lacked.

Design:
- ``ModelInvoker`` is the transport boundary. The production transport posts to
  an OpenAI-compatible ``/chat/completions`` endpoint; tests inject a fake
  transport so no network call is ever made in CI.
- Each ``ModelAgent`` has a distinct ``agent_id``, its own system prompt, and an
  explicit tool/permission allowlist. A response that requests a tool outside
  the allowlist is refused (the allowlist is enforced, not merely recorded).
- Calls carry a ``task_id`` correlation, a bounded timeout, bounded retries with
  backoff, and a bounded concurrency pool.
- Every call returns a redacted receipt (agent ID, attempt, timing, token use,
  exit status) that can be appended to the ledger.

The worker is *disabled without an API key*: it never invents a credential and
refuses to dispatch when ``api_key`` is empty.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

from blind_sniper_redaction import redact_value

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_ATTEMPTS = 3
MAX_CONCURRENCY = 5


class ModelWorkerError(RuntimeError):
    """A bounded model invocation failed or was refused."""


class ToolNotAllowedError(ModelWorkerError):
    """The model requested a tool outside its declared allowlist."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_transport(*, url: str, api_key: str, payload: dict[str, Any], timeout: int) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Blind-Sniper-Model-Worker",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
        except (ValueError, OSError):
            detail = {"error": f"HTTP {exc.code}"}
        return exc.code, detail
    except urllib.error.URLError as exc:
        raise ModelWorkerError(f"model transport failed: {exc.reason}") from exc


class ModelAgent:
    """One independent agent identity with an enforced tool allowlist."""

    def __init__(
        self,
        *,
        agent_id: str,
        system_prompt: str,
        allowed_tools: list[str],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.0,
    ) -> None:
        if not agent_id or any(ch.isspace() for ch in agent_id):
            raise ModelWorkerError("agent_id must be a non-empty token")
        if not isinstance(allowed_tools, list) or any(not isinstance(tool, str) or not tool for tool in allowed_tools):
            raise ModelWorkerError("allowed_tools must be a list of non-empty strings")
        if len(set(allowed_tools)) != len(allowed_tools):
            raise ModelWorkerError("allowed_tools must not contain duplicates")
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.allowed_tools = list(allowed_tools)
        self.model = model
        self.temperature = temperature

    def check_tools(self, requested_tools: list[str]) -> None:
        """Refuse any requested tool outside this agent's allowlist."""
        if not isinstance(requested_tools, list):
            raise ToolNotAllowedError("requested_tools must be a list")
        disallowed = sorted({tool for tool in requested_tools if tool not in self.allowed_tools})
        if disallowed:
            raise ToolNotAllowedError(
                f"agent {self.agent_id} may not use tools {disallowed}; allowed={self.allowed_tools}"
            )


class ModelInvoker:
    """Transport boundary. Swap ``transport`` in tests; never call the network there."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        transport: Callable[..., tuple[int, dict[str, Any]]] = _http_transport,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("BLIND_SNIPER_MODEL_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        if not 1 <= timeout <= 600:
            raise ModelWorkerError("timeout must be between 1 and 600 seconds")
        if not 1 <= max_attempts <= 6:
            raise ModelWorkerError("max_attempts must be between 1 and 6")
        self.timeout = timeout
        self.max_attempts = max_attempts
        self._sleep = sleep

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _invoke_once(self, agent: ModelAgent, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "model": agent.model,
            "messages": [{"role": "system", "content": agent.system_prompt}, *messages],
            "temperature": agent.temperature,
        }
        status, body = self.transport(
            url=f"{self.base_url}/chat/completions",
            api_key=self.api_key, payload=payload, timeout=self.timeout,
        )
        if status != 200:
            raise ModelWorkerError(f"model endpoint returned HTTP {status}: {redact_value(body)}")
        return body

    def invoke(
        self,
        *,
        agent: ModelAgent,
        task_id: str,
        messages: list[dict[str, Any]],
        requested_tools: list[str] | None = None,
        run_nonce: str = "run",
    ) -> dict[str, Any]:
        """Invoke one agent with fresh context, bounded retries and a receipt."""
        if not task_id or any(ch.isspace() for ch in task_id):
            raise ModelWorkerError("task_id must be a non-empty token")
        if not isinstance(messages, list) or not messages:
            raise ModelWorkerError("messages must be a non-empty list (fresh context is supplied here)")
        agent.check_tools(requested_tools or [])

        started = time.monotonic()
        last_error: str | None = None
        for attempt in range(1, self.max_attempts + 1):
            if not self.enabled:
                return self._receipt(agent, task_id, attempt, started, status="DISABLED",
                                     error="no API key configured; worker is disabled")
            try:
                body = self._invoke_once(agent, messages)
                usage = body.get("usage", {}) if isinstance(body, dict) else {}
                content = ""
                if isinstance(body, dict):
                    choices = body.get("choices") or []
                    if choices and isinstance(choices[0], dict):
                        content = str(choices[0].get("message", {}).get("content", ""))
                return self._receipt(
                    agent, task_id, attempt, started, status="PASS",
                    output=content, usage=usage,
                )
            except ModelWorkerError as exc:
                last_error = str(exc)
                if attempt < self.max_attempts:
                    self._sleep(min(2 ** (attempt - 1), 8))
        return self._receipt(agent, task_id, 0, started, status="FAIL", error=last_error)

    def _receipt(
        self, agent: ModelAgent, task_id: str, attempt: int, started: float,
        *, status: str, output: str = "", usage: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return redact_value({
            "agent_id": agent.agent_id,
            "model": agent.model,
            "task_id": task_id,
            "status": status,
            "attempt": attempt,
            "allowed_tools": agent.allowed_tools,
            "output": output,
            "usage": usage or {},
            "error": error,
            "duration_seconds": round(time.monotonic() - started, 4),
            "completed_at": _now(),
        })

    def invoke_many(
        self,
        *,
        jobs: list[dict[str, Any]],
        max_concurrency: int = 2,
    ) -> list[dict[str, Any]]:
        """Run several independent agent invocations with bounded concurrency."""
        if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int) or not 1 <= max_concurrency <= MAX_CONCURRENCY:
            raise ModelWorkerError(f"max_concurrency must be between 1 and {MAX_CONCURRENCY}")
        receipts: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
            futures = {
                pool.submit(
                    self.invoke, agent=job["agent"], task_id=job["task_id"],
                    messages=job["messages"], requested_tools=job.get("requested_tools"),
                    run_nonce=job.get("run_nonce", "run"),
                ): job["task_id"]
                for job in jobs
            }
            for future in as_completed(futures):
                receipts.append(future.result())
        return sorted(receipts, key=lambda item: item["task_id"])
