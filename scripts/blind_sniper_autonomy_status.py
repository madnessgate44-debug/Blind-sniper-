#!/usr/bin/env python3
"""Report continuous-autonomy capability state without contacting any service.

Prints, for each new adapter, whether it is enabled (secret present) or disabled,
plus the durable-queue health digest for a local ledger. Never prints a secret
value; only a boolean for whether the relevant environment variable is set.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_worker as worker  # noqa: E402
from blind_sniper_forge_mcp import ForgeMCPClient  # noqa: E402
from blind_sniper_ledger import LedgerError, TaskLedger  # noqa: E402
from blind_sniper_model_worker import ModelInvoker  # noqa: E402
from blind_sniper_openhands_cloud import OpenHandsCloudClient  # noqa: E402
from blind_sniper_queue import DurableQueue  # noqa: E402


def status() -> dict:
    model = ModelInvoker()
    openhands = OpenHandsCloudClient()
    forge = ForgeMCPClient()
    return {
        "model_worker": {"enabled": model.enabled, "secret_env": "BLIND_SNIPER_MODEL_API_KEY"},
        "openhands_cloud_v1": {"enabled": openhands.enabled, "secret_env": "OPENHANDS_CLOUD_API_KEY"},
        "forge_mcp": {"enabled": forge.enabled, "secret_env": "FORGE_MCP_TOKEN",
                      "direct_chatgpt_connector": "BLOCKED"},
        "durable_queue": {"backend": "local_ledger", "note": "logical persistence; not a resident process"},
        "trigger": {"schedule_activated": False,
                    "reason": "manual dispatch only until executor, private store and secrets are configured"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blind Sniper autonomy capability status")
    parser.add_argument("--ledger", default=".blind-sniper/state/events.jsonl")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    report = status()
    try:
        queue = DurableQueue(TaskLedger(args.ledger))
        report["queue_health"] = worker.health_digest(queue)
    except (LedgerError, OSError) as exc:
        report["queue_health"] = {"error": f"{type(exc).__name__}: {exc}"}
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
