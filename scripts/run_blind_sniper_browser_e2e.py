#!/usr/bin/env python3
"""Run a real agent-browser round trip against a local, harmless fixture."""
from __future__ import annotations

import os
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.blind_sniper_browser import BrowserAdapter

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "browser"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main() -> int:
    os.environ["BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS"] = "127.0.0.1,localhost"
    os.environ["BLIND_SNIPER_BROWSER_BLOCKED_DOMAINS"] = ""
    os.environ["BLIND_SNIPER_BROWSER_WRITE_APPROVED"] = "1"
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(FIXTURE), **kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    temp = tempfile.TemporaryDirectory()
    state_dir = Path(temp.name) / "browser-state"
    base = f"http://127.0.0.1:{server.server_port}/"
    adapter = BrowserAdapter(
        task_id="BS-BROWSER-CI-001",
        run_id=os.environ.get("GITHUB_RUN_ID", "local-browser-e2e"),
        session_id="ci_browser_e2e",
        state_dir=state_dir,
        approval_reference="CI-LOCAL-FIXTURE-ONLY",
        timeout=45,
    )
    steps = [
        ("open", "open", (base,)),
        ("snapshot-before", "snapshot", ()),
        ("screenshot", "screenshot", ("before.png",)),
        ("fill-name", "fill", ("#name", "Ada")),
        ("submit", "click", ("#submit",)),
        ("snapshot-after", "snapshot", ()),
        ("close", "close", ()),
    ]
    try:
        results = {}
        for step_id, action, args in steps:
            result = adapter.execute(action, step_id, *args)
            if result["receipt"]["exit_code"] != 0:
                raise RuntimeError(f"{action} failed: {result['error']}")
            results[step_id] = result
        if "Submitted: Ada" not in results["snapshot-after"]["output"]:
            raise AssertionError("The fixture did not reach the expected submitted state")
        screenshot = state_dir / "artifacts" / "before.png"
        if not screenshot.is_file() or screenshot.stat().st_size == 0:
            raise AssertionError("The browser screenshot artifact is missing or empty")
        run_id = os.environ.get("GITHUB_RUN_ID", "local-browser-e2e")
        receipts = state_dir / "receipts" / f"BS-BROWSER-CI-001__{run_id}.jsonl"
        lines = receipts.read_text(encoding="utf-8").splitlines()
        if len(lines) != len(steps):
            raise AssertionError(f"Expected {len(steps)} receipts, got {len(lines)}")
        print(f"PASS: real Chromium browser round trip; steps={len(steps)}; screenshot_bytes={screenshot.stat().st_size}; receipts={len(lines)}")
        return 0
    finally:
        server.shutdown()
        server.server_close()
        temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
