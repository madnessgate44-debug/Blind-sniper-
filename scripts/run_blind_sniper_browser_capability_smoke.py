#!/usr/bin/env python3
"""Real Chromium smoke test for screenshots and clipboard copy/paste through native dispatch."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_browser_dispatch import dispatch_browser_action
from blind_sniper_ledger import TaskLedger


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main() -> int:
    os.environ["BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS"] = "127.0.0.1"
    os.environ["BLIND_SNIPER_BROWSER_BLOCKED_DOMAINS"] = ""
    os.environ["BLIND_SNIPER_BROWSER_WRITE_APPROVED"] = "1"
    with tempfile.TemporaryDirectory(prefix="blind-sniper-browser-capabilities-") as temporary:
        root = Path(temporary)
        site = root / "site"
        site.mkdir()
        (site / "index.html").write_text("""<!doctype html>
<html><head><meta charset="utf-8"><title>Blind Sniper browser capability fixture</title></head>
<body>
  <h1>Browser capability fixture</h1>
  <p id="copy-source">Blind Sniper copy proof 2026</p>
  <button id="select-copy" onclick="const r=document.createRange();r.selectNodeContents(document.querySelector('#copy-source'));const s=getSelection();s.removeAllRanges();s.addRange(r)">Select copy proof</button>
  <label for="paste-target">Paste target</label>
  <textarea id="paste-target"></textarea>
</body></html>""", encoding="utf-8")
        handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(site), **kwargs)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        state_dir = Path(os.environ.get("BLIND_SNIPER_BROWSER_STATE_DIR", ".blind-sniper/browser-capabilities")).resolve()
        state_dir.mkdir(parents=True, exist_ok=True)
        ledger = TaskLedger(state_dir / "state" / "events.jsonl")
        task_id = "BS-BROWSER-CAPABILITY-SMOKE"
        owner_id = "github-actions-capability-smoke"
        run_id = os.environ.get("GITHUB_RUN_ID", "local")
        session_id = "capability" + str(os.getpid())
        ledger.append(
            task_id=task_id, event_type="TASK_CREATED",
            payload={"state": {"task_id": task_id, "status": "EXECUTING",
                               "implementer_id": owner_id, "events": []}},
            idempotency_key=f"{task_id}:created",
        )
        lease = ledger.claim_task(task_id=task_id, owner_id=owner_id, lease_seconds=900,
                                  idempotency_key=f"{task_id}:lease")
        if not lease.get("claimed"):
            raise RuntimeError("Could not claim browser capability test lease")

        def act(step: str, action: str, *args: str):
            result = dispatch_browser_action(
                ledger=ledger, task_id=task_id, owner_id=owner_id, run_id=str(run_id),
                session_id=session_id, step_id=step, action=action, action_args=list(args),
                state_dir=state_dir, timeout=60,
                approval_reference="CI-LOCAL-FIXTURE-ONLY",
            )
            if result["receipt"].get("exit_code") != 0:
                raise RuntimeError(f"{action} failed: {result.get('error', '')[:1000]}")
            return result

        try:
            url = f"http://127.0.0.1:{server.server_port}/"
            act("open-fixture", "open", url)
            shot = act("capture-fixture-screenshot", "screenshot", "capability-smoke.png")
            image_path = state_dir / "artifacts" / "capability-smoke.png"
            if not image_path.is_file() or image_path.stat().st_size < 1000:
                raise RuntimeError("Screenshot file missing or implausibly small")

            paste_text = "Blind Sniper paste proof 2026"
            act("clipboard-write-proof", "clipboard-write", paste_text)
            act("focus-paste-target", "click", "#paste-target")
            act("clipboard-paste-proof", "clipboard-paste")
            pasted_snapshot = act("verify-pasted-text", "snapshot").get("output", "")
            if paste_text not in pasted_snapshot:
                raise RuntimeError("Pasted text was not present in the browser accessibility snapshot")

            act("select-copy-source", "click", "#select-copy")
            act("clipboard-copy-proof", "clipboard-copy")
            copied = act("read-copied-text", "clipboard-read").get("output", "")
            if "Blind Sniper copy proof 2026" not in copied:
                raise RuntimeError("Copied selection was not returned by clipboard read")

            print(f"PASS: screenshot_bytes={image_path.stat().st_size}")
            print(f"PASS: paste_text_verified={paste_text!r}")
            print("PASS: copied_selection_verified='Blind Sniper copy proof 2026'")
            print(f"PASS: screenshot_artifact={image_path}")
            return 0
        finally:
            try:
                act("close-browser", "close")
            finally:
                ledger.release_task(task_id=task_id, owner_id=owner_id,
                                    idempotency_key=f"{task_id}:lease-release")
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
