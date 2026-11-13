#!/usr/bin/env python3
"""Read-only live-site smoke test through Blind Sniper's lease-gated browser path."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_browser_dispatch import dispatch_browser_action
from blind_sniper_ledger import TaskLedger

TARGET_URL = os.environ.get("BLIND_SNIPER_MISS_NOOR_URL", "https://amina-nine-sepia.vercel.app/")
EXPECTED_HOST = urlsplit(TARGET_URL).hostname
OWNER_ID = "github-actions-browser-smoke"


def main() -> int:
    if not EXPECTED_HOST:
        raise RuntimeError("The Miss Noor target URL has no hostname")
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    safe_run = re.sub(r"[^A-Za-z0-9_.:-]", "-", f"miss-noor-{run_id}-{attempt}")
    task_id = f"BS-MISS-NOOR-{safe_run}"
    session_id = re.sub(r"[^A-Za-z0-9_-]", "-", f"missnoor{run_id}{attempt}")[:64]
    state_dir = Path(os.environ.get("BLIND_SNIPER_BROWSER_STATE_DIR", ".blind-sniper/browser-live")).resolve()
    ledger = TaskLedger(state_dir / "state" / "events.jsonl")
    task_state = {
        "task_id": task_id,
        "status": "EXECUTING",
        "implementer_id": OWNER_ID,
        "events": [],
    }
    ledger.append(
        task_id=task_id,
        event_type="TASK_CREATED",
        payload={"state": task_state},
        idempotency_key=f"{task_id}:created",
    )
    lease = ledger.claim_task(
        task_id=task_id,
        owner_id=OWNER_ID,
        lease_seconds=900,
        idempotency_key=f"{task_id}:lease",
    )
    if not lease.get("claimed"):
        raise RuntimeError("Could not claim the native task lease")

    def run(step_id: str, action: str, args: tuple[str, ...] = ()):
        result = dispatch_browser_action(
            ledger=ledger,
            task_id=task_id,
            owner_id=OWNER_ID,
            run_id=safe_run,
            session_id=session_id,
            step_id=step_id,
            action=action,
            action_args=list(args),
            state_dir=state_dir,
            timeout=60,
        )
        if result["receipt"].get("exit_code") != 0:
            raise RuntimeError(f"{action} failed: {result.get('error', '')[:1500]}")
        return result

    try:
        opened = run("open-miss-noor", "open", (TARGET_URL,))
        snapshot = run("capture-accessibility-tree", "snapshot")
        screenshot = run("capture-screenshot", "screenshot", ("miss-noor-home.png",))
        current_url = opened["receipt"].get("observed_url") or ""
        parsed = urlsplit(current_url.replace("/[REDACTED]", "/"))
        if parsed.hostname != EXPECTED_HOST:
            raise RuntimeError(f"Unexpected final browser host: {parsed.hostname!r}")
        snapshot_text = snapshot.get("output", "")
        if not snapshot_text.strip():
            raise RuntimeError("Browser returned an empty accessibility snapshot")
        artifacts = state_dir / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "miss-noor-accessibility-snapshot.txt").write_text(snapshot_text, encoding="utf-8")
        (artifacts / "miss-noor-inspection.json").write_text(
            json.dumps({
                "target_url": TARGET_URL,
                "final_url": current_url.strip(),
                "host": EXPECTED_HOST,
                "snapshot_characters": len(snapshot_text),
                "screenshot_bytes": (artifacts / "miss-noor-home.png").stat().st_size
                    if (artifacts / "miss-noor-home.png").exists() else 0,
                "open_receipt": opened["receipt"],
                "snapshot_receipt": snapshot["receipt"],
                "screenshot_receipt": screenshot["receipt"],
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        image = artifacts / "miss-noor-home.png"
        if not image.is_file() or image.stat().st_size == 0:
            raise RuntimeError("Browser screenshot artifact is missing or empty")
        print(f"PASS: Blind Sniper opened {TARGET_URL}")
        print(f"PASS: final_url={current_url.strip()}")
        print(f"PASS: accessibility_snapshot_characters={len(snapshot_text)}")
        print(f"PASS: screenshot_bytes={image.stat().st_size}")
        print(f"ARTIFACTS: {artifacts}")
        return 0
    finally:
        try:
            run("close-browser", "close")
        finally:
            ledger.release_task(
                task_id=task_id,
                owner_id=OWNER_ID,
                idempotency_key=f"{task_id}:lease-release",
            )


if __name__ == "__main__":
    raise SystemExit(main())
