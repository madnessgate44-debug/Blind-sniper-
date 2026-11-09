#!/usr/bin/env python3
"""Receipt schema for the durable allowlisted executor workflow.

A receipt is the durable, machine-readable record of one allowlisted command run
by ``.github/workflows/blind-sniper-executor.yml``. The schema is intentionally
closed: exactly the seven fields below, no more, no fewer.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# The only commands the executor may run. Raw shell strings are never accepted.
ALLOWED_COMMANDS = ("validate-runtime", "run-tests")

# Closed field set for a receipt.
RECEIPT_FIELDS = (
    "task_id",
    "command",
    "exit_code",
    "run_id",
    "run_url",
    "timestamp",
    "status",
)

TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
RUN_ID_PATTERN = re.compile(r"^[0-9]+$")
TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)


class ReceiptError(ValueError):
    """Raised when a receipt does not satisfy the schema."""


def status_for_exit_code(exit_code: int) -> str:
    return "PASS" if exit_code == 0 else "FAIL"


def build_receipt(
    *,
    task_id: str,
    command: str,
    exit_code: int,
    run_id: str,
    run_url: str,
    timestamp: str | None = None,
) -> dict:
    """Build a receipt dict and validate it before returning."""
    receipt = {
        "task_id": task_id,
        "command": command,
        "exit_code": exit_code,
        "run_id": run_id,
        "run_url": run_url,
        "timestamp": timestamp
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status_for_exit_code(exit_code),
    }
    validate_receipt(receipt)
    return receipt


def validate_receipt(receipt: dict) -> None:
    """Raise ReceiptError unless *receipt* exactly matches the schema."""
    if not isinstance(receipt, dict):
        raise ReceiptError("receipt must be a JSON object")

    keys = set(receipt)
    expected = set(RECEIPT_FIELDS)
    missing = expected - keys
    extra = keys - expected
    if missing:
        raise ReceiptError(f"receipt missing fields: {sorted(missing)}")
    if extra:
        raise ReceiptError(f"receipt has unexpected fields: {sorted(extra)}")

    task_id = receipt["task_id"]
    if not isinstance(task_id, str) or not TASK_ID_PATTERN.match(task_id):
        raise ReceiptError("task_id must match [A-Za-z0-9._-]{1,64}")

    command = receipt["command"]
    if command not in ALLOWED_COMMANDS:
        raise ReceiptError(f"command must be one of {list(ALLOWED_COMMANDS)}")

    exit_code = receipt["exit_code"]
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise ReceiptError("exit_code must be an integer")

    run_id = receipt["run_id"]
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.match(run_id):
        raise ReceiptError("run_id must be a numeric string")

    run_url = receipt["run_url"]
    if not isinstance(run_url, str) or not run_url.startswith("https://"):
        raise ReceiptError("run_url must be an https URL")

    timestamp = receipt["timestamp"]
    if not isinstance(timestamp, str) or not TIMESTAMP_PATTERN.match(timestamp):
        raise ReceiptError("timestamp must be an ISO-8601 UTC instant ending in Z")

    status = receipt["status"]
    if status not in ("PASS", "FAIL"):
        raise ReceiptError("status must be PASS or FAIL")
    if status != status_for_exit_code(exit_code):
        raise ReceiptError("status must agree with exit_code")


def write_receipt(receipt: dict, output_dir: str | Path, task_id: str) -> Path:
    validate_receipt(receipt)
    target_dir = Path(output_dir) / "ops" / "receipts"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{task_id}.json"
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a durable executor receipt")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--command", required=True, choices=ALLOWED_COMMANDS)
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    receipt = build_receipt(
        task_id=args.task_id,
        command=args.command,
        exit_code=args.exit_code,
        run_id=args.run_id,
        run_url=args.run_url,
    )
    target = write_receipt(receipt, args.output_dir, args.task_id)
    print(json.dumps(receipt, sort_keys=True))
    print(f"receipt written: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
