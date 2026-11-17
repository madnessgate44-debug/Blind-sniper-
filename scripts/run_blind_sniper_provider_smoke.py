#!/usr/bin/env python3
"""One-shot, synthetic provider connectivity smoke test.

This command invokes exactly one read-only native model agent with a fixed,
non-sensitive prompt. It does not create a queue task, enable tools, write files,
or print provider output or credentials.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable, TextIO

from blind_sniper_model_worker import AgentSpec, ModelTask, ModelWorker, NativeModelInvoker

EXPECTED_RESPONSE = "BLIND_SNIPER_PROVIDER_OK"
TASK_ID = "BS-PROVIDER-SMOKE-001"


def run_smoke(
    *,
    environ: dict[str, str] | None = None,
    invoker_factory: Callable[..., Any] = NativeModelInvoker,
    output: TextIO | None = None,
) -> int:
    env = os.environ if environ is None else environ
    stream = output or sys.stdout
    api_key = env.get("BLIND_SNIPER_MODEL_API_KEY", "").strip()
    if not api_key:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": "BLIND_SNIPER_MODEL_API_KEY secret is not configured",
            "task_id": TASK_ID,
        }, sort_keys=True), file=stream)
        return 2

    base_url = env.get(
        "BLIND_SNIPER_MODEL_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ).strip()
    model = env.get("BLIND_SNIPER_MODEL_NAME", "gemini-3.8-flash").strip()
    if not base_url or not model:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": "Provider base URL and model name must be configured",
            "task_id": TASK_ID,
        }, sort_keys=True), file=stream)
        return 2

    try:
        invoker = invoker_factory(
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_output_tokens=128,
            max_tool_rounds=0,
            max_tool_calls=0,
        )
        worker = ModelWorker(
            invoker,
            max_concurrency=1,
            timeout_seconds=60,
            max_retries=0,
        )
        spec = AgentSpec(
            agent_id="researcher",
            fresh_context=True,
            tool_allowlist=(),
            permission_profile="read_only",
        )
        task = ModelTask(
            task_id=TASK_ID,
            agent_id="researcher",
            objective=(
                "This is a synthetic connectivity test. Reply with exactly "
                f"{EXPECTED_RESPONSE} and no other text."
            ),
            payload={"purpose": "synthetic provider connectivity test; no private data"},
            lease_seconds=60,
        )
        result = worker.run([spec], [task])
        receipt = result["receipts"][0]
        output_match = (
            receipt.get("status") == "PASS"
            and receipt.get("output_text", "").strip() == EXPECTED_RESPONSE
        )
        summary = {
            "status": "PASS" if output_match else "FAIL",
            "provider": receipt.get("provider"),
            "model": receipt.get("model") or model,
            "task_id": receipt.get("task_id"),
            "agent_id": receipt.get("agent_id"),
            "run_id": receipt.get("run_id"),
            "attempts": receipt.get("attempts"),
            "output_match": output_match,
            "output_digest": receipt.get("output_digest"),
        }
        print(json.dumps(summary, sort_keys=True), file=stream)
        return 0 if output_match else 1
    except Exception as exc:
        # Do not print exception messages: providers may echo request metadata.
        print(json.dumps({
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "task_id": TASK_ID,
            "model": model,
        }, sort_keys=True), file=stream)
        return 1


def main() -> int:
    return run_smoke()


if __name__ == "__main__":
    raise SystemExit(main())
