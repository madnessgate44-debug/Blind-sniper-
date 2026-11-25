#!/usr/bin/env python3
"""One-shot proof that the native daemon runs a synthetic task end to end.

Plumbing only: the model is a local stub on 127.0.0.1, the task is synthetic, no
network, no credentials. It does NOT prove a real model, notifications or a
resident service. Only aggregate health counts are written to --output-dir;
receipts, ledger and notifications stay in a runner-local private directory.
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class _Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers.get("content-length", 0)))
        body = json.dumps({"choices": [{"message": {"content": "STUB-OK synthetic result"}, "finish_reason": "stop"}]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    server = http.server.HTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / "state"
        (state / "tasks").mkdir(parents=True, mode=0o700)
        state.chmod(0o700)
        task = state / "tasks" / "SMOKE-1.json"
        task.write_text(json.dumps({
            "task_id": "SMOKE-1", "agent_id": "researcher",
            "objective": "synthetic one-shot daemon smoke", "payload": {"note": "synthetic"},
        }), encoding="utf-8")
        task.chmod(0o600)
        env = {k: v for k, v in os.environ.items() if not k.startswith("BLIND_SNIPER_")}
        env["BLIND_SNIPER_MODEL_BASE_URL"] = f"http://127.0.0.1:{server.server_address[1]}"
        env["BLIND_SNIPER_MODEL_NAME"] = "local-stub"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "blind_sniper_daemon.py"), "--state-dir", str(state),
             "--owner-id", "smoke", "--once", "--workspace-root", str(ROOT)],
            env=env, capture_output=True, text=True, timeout=120,
        )
        health = json.loads((state / "health.json").read_text(encoding="utf-8"))
        receipts = list((state / "receipts").glob("*.json"))
        summary = {
            "scope": "plumbing only: local stub model, synthetic task, no network",
            "exit_code": proc.returncode,
            "status": health.get("status"),
            "counts": health.get("counts"),
            "receipt_files": len(receipts),
        }
        (out / "daemon-once-smoke.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    server.shutdown()
    ok = summary["status"] == "HEALTHY" and summary["counts"]["completed"] == 1 and summary["counts"]["errors"] == 0 and summary["counts"]["failed"] == 0
    print(json.dumps(summary, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
