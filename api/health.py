"""Read-only deployment health endpoint for the native Blind Sniper host."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler


def health_payload() -> dict[str, object]:
    """Report only what this stateless Vercel function can prove."""
    return {
        "service": "blind-sniper",
        "component": "vercel-http-host",
        "status": "ok",
        "execution_mode": "event-driven",
        "worker": "not_activated",
        "task_execution_enabled": False,
        "reason": "Native task execution remains disabled until private durable storage and a configured model provider are connected.",
    }


class handler(BaseHTTPRequestHandler):
    """Vercel Python runtime entrypoint; intentionally read-only."""

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0].rstrip("/") != "/api/health":
            self.send_error(404)
            return
        body = json.dumps(health_payload(), separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        self.send_error(405, "Method Not Allowed")

    def do_PUT(self) -> None:
        self.send_error(405, "Method Not Allowed")

    def do_DELETE(self) -> None:
        self.send_error(405, "Method Not Allowed")
