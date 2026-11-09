#!/usr/bin/env python3
"""Two-job persistent-host acceptance probe for one registered Oracle runner.

Phase 'open' is run by job 1. Phase 'verify' is run by job 2 on the same
single self-hosted runner. The browser daemon and task ledger must survive
between jobs; a fresh browser session in job 2 is a failure.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_browser import BrowserAdapter
from blind_sniper_browser_dispatch import dispatch_browser_action
from blind_sniper_ledger import TaskLedger

OWNER_ID = "blind-sniper-oracle-runner"
FIXTURE_URL = f"http://127.0.0.1:{int(os.environ.get('BLIND_SNIPER_FIXTURE_PORT', '8765'))}/"


def context():
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if not run_id.isdigit():
        raise RuntimeError("GITHUB_RUN_ID must be a numeric workflow run identifier")
    root = Path(os.environ.get("BLIND_SNIPER_BROWSER_STATE_DIR", "/var/lib/blind-sniper/browser")).resolve()
    browser_dir = root / f"host-persistence-{run_id}"
    ledger = TaskLedger(root.parent / "state" / "events.jsonl")
    task_id = f"BS-HOST-PERSISTENCE-{run_id}"
    run_key = f"host-persistence-{run_id}"
    session_id = f"host_persist_{run_id}"
    return ledger, task_id, run_key, session_id, browser_dir


def dispatch(ledger, task_id, run_key, session_id, browser_dir, step_id, action, args=()):
    return dispatch_browser_action(
        ledger=ledger,
        task_id=task_id,
        owner_id=OWNER_ID,
        run_id=run_key,
        session_id=session_id,
        step_id=step_id,
        action=action,
        action_args=list(args),
        state_dir=browser_dir,
        timeout=45,
        approval_reference="HOST-PERSISTENCE-READONLY",
        adapter_factory=BrowserAdapter,
    )


def open_phase():
    ledger, task_id, run_key, session_id, browser_dir = context()
    if ledger.task_history(task_id)["events"]:
        raise RuntimeError("Persistence probe task already exists for this workflow run")
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
        lease_seconds=3600,
        idempotency_key=f"{task_id}:lease",
    )
    if not lease["claimed"]:
        raise RuntimeError("Could not claim persistent-host probe task lease")
    result = dispatch(ledger, task_id, run_key, session_id, browser_dir, "open", "open", (FIXTURE_URL,))
    if result["receipt"]["exit_code"] != 0:
        raise RuntimeError(f"Host job 1 could not open the fixture: {result['error']} {result['output'][:500]}")
    snapshot = dispatch(ledger, task_id, run_key, session_id, browser_dir, "snapshot-before-handoff", "snapshot")
    if snapshot["receipt"]["exit_code"] != 0 or "Blind Sniper Browser Fixture" not in snapshot["output"]:
        raise RuntimeError("Host job 1 did not observe the expected fixture content")
    print(f"PASS: job 1 opened browser session {session_id}; state={browser_dir}; ledger={ledger.path}")


def verify_phase():
    ledger, task_id, run_key, session_id, browser_dir = context()
    status = ledger.lease_status(task_id)
    if not status or status.get("owner_id") != OWNER_ID:
        raise RuntimeError("Persistent task lease is missing or owned by another runner")
    result = dispatch(ledger, task_id, run_key, session_id, browser_dir, "cross-job-snapshot", "snapshot")
    if result["receipt"]["exit_code"] != 0:
        raise RuntimeError(f"Host job 2 could not recover the browser session: {result['error']} {result['output'][:500]}")
    if "Blind Sniper Browser Fixture" not in result["output"]:
        raise RuntimeError("Host job 2 did not recover the original page; browser session was not persistent")
    closed = dispatch(ledger, task_id, run_key, session_id, browser_dir, "close", "close")
    if closed["receipt"]["exit_code"] != 0:
        raise RuntimeError("Persistent browser session failed to close")
    released = ledger.release_task(
        task_id=task_id,
        owner_id=OWNER_ID,
        idempotency_key=f"{task_id}:lease-release",
    )
    if not released["released"]:
        raise RuntimeError("Persistent-host task lease was not released")
    print("PASS: job 2 recovered the same Chromium page across the GitHub Actions job boundary; session closed and lease released")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("open", "verify"), required=True)
    args = parser.parse_args()
    os.environ.setdefault("BLIND_SNIPER_BROWSER_IDLE_TIMEOUT", "0")
    os.environ.setdefault("BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS", "127.0.0.1,localhost")
    os.environ.setdefault("BLIND_SNIPER_BROWSER_WRITE_APPROVED", "0")
    if args.phase == "open":
        open_phase()
    else:
        verify_phase()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
