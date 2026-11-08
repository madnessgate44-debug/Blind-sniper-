#!/usr/bin/env python3
"""Run two real browser cycles through the native lease-gated dispatcher.

Each cycle also injects a process interruption after a harmless snapshot,
proves that a started-only step is not replayed, reconciles its persisted
receipt, and then continues with a new step.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.blind_sniper_browser import BrowserAdapter
from scripts.blind_sniper_browser_dispatch import (
    BrowserDispatchError,
    dispatch_browser_action,
)
from scripts.blind_sniper_ledger import TaskLedger

FIXTURE = ROOT / "tests" / "fixtures" / "browser"
OWNER_ID = "ci-browser-runner"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class SimulatedInterruption(RuntimeError):
    pass


class InterruptAfterSnapshot(BrowserAdapter):
    """Execute a harmless real snapshot, persist its receipt, then simulate a crash."""

    def execute(self, action: str, step_id: str, *args: str):
        result = super().execute(action, step_id, *args)
        if action != "snapshot":
            raise AssertionError("interruption adapter is restricted to read-only snapshot")
        if result["receipt"]["exit_code"] != 0:
            raise AssertionError("snapshot before simulated interruption failed")
        raise SimulatedInterruption("simulated worker loss after browser action, before ledger completion")


def _dispatch(ledger, *, task_id, run_id, session_id, step_id, action, args, state_dir, adapter_factory=BrowserAdapter):
    return dispatch_browser_action(
        ledger=ledger,
        task_id=task_id,
        owner_id=OWNER_ID,
        run_id=run_id,
        session_id=session_id,
        step_id=step_id,
        action=action,
        action_args=list(args),
        state_dir=state_dir,
        timeout=45,
        approval_reference="CI-LOCAL-FIXTURE-ONLY",
        adapter_factory=adapter_factory,
    )


def run_cycle(*, cycle: int, base_url: str, root_state_dir: Path, base_run_id: str) -> tuple[int, int]:
    task_id = f"BS-BROWSER-CI-{cycle:03d}"
    run_id = f"{base_run_id}-{cycle}"
    session_id = f"ci_browser_e2e_{cycle}"
    cycle_dir = root_state_dir / f"cycle-{cycle}"
    browser_dir = cycle_dir / "browser"
    ledger_path = cycle_dir / "state" / "events.jsonl"
    ledger = TaskLedger(ledger_path)

    state = {
        "task_id": task_id,
        "status": "EXECUTING",
        "implementer_id": OWNER_ID,
        "events": [],
    }
    ledger.append(
        task_id=task_id,
        event_type="TASK_CREATED",
        payload={"state": state},
        idempotency_key=f"{task_id}:created",
    )
    lease = ledger.claim_task(
        task_id=task_id,
        owner_id=OWNER_ID,
        lease_seconds=900,
        idempotency_key=f"{task_id}:lease",
    )
    if not lease["claimed"]:
        raise RuntimeError("E2E runner could not claim its native task lease")

    steps = [
        ("open", "open", (base_url,)),
        ("snapshot-before", "snapshot", ()),
        ("screenshot", "screenshot", (f"before-{cycle}.png",)),
        ("fill-name", "fill", ("#name", f"Ada-{cycle}")),
        ("submit", "click", ("#submit",)),
        ("snapshot-after", "snapshot", ()),
    ]
    results = {}
    for step_id, action, args in steps:
        result = _dispatch(
            ledger, task_id=task_id, run_id=run_id, session_id=session_id,
            step_id=step_id, action=action, args=args, state_dir=browser_dir,
        )
        if result["receipt"]["exit_code"] != 0:
            raise RuntimeError(f"{action} failed: {result['error'][:2000]}")
        results[step_id] = result

    expected_text = f"Submitted: Ada-{cycle}"
    if expected_text not in results["snapshot-after"]["output"]:
        raise AssertionError("The fixture did not reach the expected submitted state")

    screenshot = browser_dir / "artifacts" / f"before-{cycle}.png"
    if not screenshot.is_file() or screenshot.stat().st_size == 0:
        raise AssertionError("The browser screenshot artifact is missing or empty")

    # Simulate loss after the external browser action and local receipt, but before
    # BROWSER_ACTION_COMPLETED is appended to the authoritative task ledger.
    interrupted_step = "snapshot-interrupted"
    try:
        _dispatch(
            ledger, task_id=task_id, run_id=run_id, session_id=session_id,
            step_id=interrupted_step, action="snapshot", args=(),
            state_dir=browser_dir, adapter_factory=InterruptAfterSnapshot,
        )
    except SimulatedInterruption:
        pass
    else:
        raise AssertionError("The interruption injection did not fire")

    receipts_file = browser_dir / "receipts" / f"{task_id}__{run_id}.jsonl"
    receipts = [json.loads(line) for line in receipts_file.read_text(encoding="utf-8").splitlines()]
    interrupted_receipt = next((row for row in receipts if row.get("step_id") == interrupted_step), None)
    if not interrupted_receipt or interrupted_receipt.get("exit_code") != 0:
        raise AssertionError("The interrupted browser action receipt was not durably written")

    # A retry with the same correlation tuple must be rejected before constructing
    # an adapter, proving the external action cannot be blindly replayed.
    adapter_constructions = 0

    def should_not_construct(**kwargs):
        nonlocal adapter_constructions
        adapter_constructions += 1
        return BrowserAdapter(**kwargs)

    try:
        _dispatch(
            ledger, task_id=task_id, run_id=run_id, session_id=session_id,
            step_id=interrupted_step, action="snapshot", args=(),
            state_dir=browser_dir, adapter_factory=should_not_construct,
        )
    except BrowserDispatchError:
        pass
    else:
        raise AssertionError("Started-only browser action was incorrectly replayed")
    if adapter_constructions != 0:
        raise AssertionError("Replay rejection happened after browser adapter construction")

    ledger.append(
        task_id=task_id,
        event_type="BROWSER_ACTION_RECONCILED",
        payload={
            "owner_id": OWNER_ID,
            "run_id": run_id,
            "session_id": session_id,
            "step_id": interrupted_step,
            "resolution": "verified_persisted_read_only_receipt_no_replay",
            "receipt_exit_code": interrupted_receipt["exit_code"],
        },
        idempotency_key=f"browser:{run_id}:{session_id}:{interrupted_step}:reconciled",
    )

    closed = _dispatch(
        ledger, task_id=task_id, run_id=run_id, session_id=session_id,
        step_id="close", action="close", args=(), state_dir=browser_dir,
    )
    if closed["receipt"]["exit_code"] != 0:
        raise RuntimeError("Browser session did not close cleanly")

    released = ledger.release_task(
        task_id=task_id,
        owner_id=OWNER_ID,
        idempotency_key=f"{task_id}:lease-release",
    )
    if not released["released"]:
        raise AssertionError("E2E task lease was not released by its owner")

    history = ledger.task_history(task_id)
    events = history["events"]
    started = [row for row in events if row["event_type"] == "BROWSER_ACTION_STARTED"]
    completed = [row for row in events if row["event_type"] == "BROWSER_ACTION_COMPLETED"]
    reconciled = [row for row in events if row["event_type"] == "BROWSER_ACTION_RECONCILED"]
    if len(started) != 8 or len(completed) != 7 or len(reconciled) != 1:
        raise AssertionError(
            f"Unexpected native ledger counts: started={len(started)}, "
            f"completed={len(completed)}, reconciled={len(reconciled)}"
        )
    # Re-read after close so the final receipt is included.
    receipts = [json.loads(line) for line in receipts_file.read_text(encoding="utf-8").splitlines()]
    if len(receipts) != 8:
        raise AssertionError(f"Expected 8 browser receipts, got {len(receipts)}")

    print(
        f"PASS: native browser cycle {cycle}; native_started={len(started)}; "
        f"native_completed={len(completed)}; interrupted_reconciled={len(reconciled)}; "
        f"receipts={len(receipts)}; screenshot_bytes={screenshot.stat().st_size}"
    )
    return len(receipts), screenshot.stat().st_size


def main() -> int:
    os.environ["BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS"] = "127.0.0.1,localhost"
    os.environ["BLIND_SNIPER_BROWSER_BLOCKED_DOMAINS"] = ""
    os.environ["BLIND_SNIPER_BROWSER_WRITE_APPROVED"] = "1"

    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(FIXTURE), **kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    root_state_dir = Path(
        os.environ.get("BLIND_SNIPER_BROWSER_STATE_DIR", ".blind-sniper/browser")
    ).resolve()
    base_url = f"http://127.0.0.1:{server.server_port}/"
    base_run_id = os.environ.get("GITHUB_RUN_ID", "local-browser-e2e")

    try:
        total_receipts = 0
        total_screenshot_bytes = 0
        for cycle in (1, 2):
            receipts, screenshot_bytes = run_cycle(
                cycle=cycle,
                base_url=base_url,
                root_state_dir=root_state_dir,
                base_run_id=base_run_id,
            )
            total_receipts += receipts
            total_screenshot_bytes += screenshot_bytes
        print(
            "PASS: two consecutive native Chromium cycles; "
            f"receipts={total_receipts}; screenshot_bytes={total_screenshot_bytes}; "
            "each cycle included a started-only interruption, no-replay check and reconciliation"
        )
        return 0
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
