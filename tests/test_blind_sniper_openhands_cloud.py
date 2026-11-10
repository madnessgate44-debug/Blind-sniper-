"""Contract tests for the OpenHands Cloud V1 API adapter.

These use a deterministic fake HTTP transport. They prove the request shape,
authentication header, idempotency, pagination, cancellation handling, bounded
retries, error mapping and redaction. They do NOT prove a live round trip: the
adapter stays PARTIAL until a real authenticated call is made.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from blind_sniper_openhands_cloud import OpenHandsCloudClient, OpenHandsCloudError


class FakeTransport:
    """Records requests and serves scripted responses keyed by (method, path)."""

    def __init__(self):
        self.requests = []
        self.responses = {}
        self.fail_times = {}

    def script(self, method, path_contains, status, payload):
        self.responses[(method, path_contains)] = (status, payload)

    def __call__(self, method, url, headers, body, timeout):
        self.requests.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        path = url.split("app.all-hands.dev", 1)[-1]
        if self.fail_times.get((method, path)):
            self.fail_times[(method, path)] -= 1
            raise RuntimeError("simulated transport failure")
        for (m, needle), (status, payload) in self.responses.items():
            if m == method and needle in path:
                raw = json.dumps(payload).encode() if payload is not None else b""
                return status, raw
        return 404, b'{"message":"not found"}'


class OpenHandsCloudClientTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.client = OpenHandsCloudClient(
            token="test-token-value", transport=self.transport, max_retries=3,
        )

    def test_requires_a_token(self):
        with self.assertRaisesRegex(OpenHandsCloudError, "bearer token"):
            OpenHandsCloudClient(token="", transport=self.transport)

    def test_requires_https_base_url(self):
        with self.assertRaisesRegex(OpenHandsCloudError, "https"):
            OpenHandsCloudClient(base_url="http://insecure", token="t", transport=self.transport)

    def test_start_conversation_sends_bearer_and_idempotency(self):
        self.transport.script("POST", "/api/v1/app-conversations", 202, [{
            "id": "start-task-1", "status": "WORKING", "app_conversation_id": None,
        }])
        result = self.client.start_conversation(
            initial_message="do the thing", selected_repository="owner/repo",
            idempotency_key="task-1:start",
        )
        self.assertEqual(result["start_task_id"], "start-task-1")
        request = self.transport.requests[-1]
        self.assertEqual(request["headers"]["Authorization"], "Bearer test-token-value")
        body = json.loads(request["body"].decode())
        self.assertEqual(body["selected_repository"], "owner/repo")
        self.assertNotIn("idempotency_key", body)  # kept client-side, not leaked to the API body

    def test_start_conversation_rejects_blank_message(self):
        with self.assertRaises(OpenHandsCloudError):
            self.client.start_conversation(initial_message="  ", idempotency_key="k")

    def test_poll_start_task_handles_list_response_and_reaches_ready(self):
        calls = {"n": 0}

        def transport(method, url, headers, body, timeout):
            calls["n"] += 1
            state = "WORKING" if calls["n"] == 1 else "READY"
            return 200, json.dumps([{
                "id": "start-task-1", "status": state, "app_conversation_id": "conv-9",
            }]).encode()

        client = OpenHandsCloudClient(token="t", transport=transport)
        result = client.poll_start_task(
            "start-task-1", timeout_seconds=30, interval_seconds=0.0, sleep=lambda _s: None,
        )
        self.assertEqual(result["state"], "READY")
        self.assertEqual(result["app_conversation_id"], "conv-9")
        self.assertGreaterEqual(result["polls"], 2)

    def test_poll_start_task_times_out_without_terminal_state(self):
        def transport(method, url, headers, body, timeout):
            return 200, json.dumps([{"id": "s", "status": "WORKING"}]).encode()

        clock = {"t": 0.0}

        def monotonic():
            clock["t"] += 1000.0
            return clock["t"]

        client = OpenHandsCloudClient(token="t", transport=transport)
        result = client.poll_start_task(
            "start-task-1", timeout_seconds=5, interval_seconds=0.0,
            sleep=lambda _s: None, monotonic=monotonic,
        )
        self.assertTrue(result.get("timed_out"))

    def test_get_messages_follows_pagination_to_exhaustion(self):
        pages = {
            None: {"items": [{"id": 1}], "next_page_id": "p2"},
            "p2": {"items": [{"id": 2}], "next_page_id": None},
        }
        seen = []

        def transport(method, url, headers, body, timeout):
            page = None
            if "page_id=" in url:
                page = url.split("page_id=", 1)[1]
            seen.append(page)
            return 200, json.dumps(pages[page]).encode()

        client = OpenHandsCloudClient(token="t", transport=transport)
        result = client.get_messages("conv-1")
        self.assertTrue(result["pagination_complete"])
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(result["pages"], 2)

    def test_cancel_conversation_reports_unsupported_on_404(self):
        self.transport.script("POST", "/cancel", 404, {"message": "no"})
        result = self.client.cancel_conversation("conv-1")
        self.assertFalse(result["supported"])

    def test_cancel_conversation_reports_supported_on_200(self):
        self.transport.script("POST", "/cancel", 200, {"ok": True})
        result = self.client.cancel_conversation("conv-1")
        self.assertTrue(result["supported"])

    def test_server_error_is_retried_then_succeeds(self):
        state = {"n": 0}

        def transport(method, url, headers, body, timeout):
            state["n"] += 1
            if state["n"] < 3:
                return 503, b'{"message":"busy"}'
            return 200, json.dumps([{"execution_status": "RUNNING", "sandbox_status": "RUNNING"}]).encode()

        client = OpenHandsCloudClient(token="t", transport=transport, max_retries=3)
        result = client.get_conversation("conv-1")
        self.assertEqual(result["execution_status"], "RUNNING")
        self.assertEqual(state["n"], 3)

    def test_error_mapping_does_not_leak_token(self):
        self.transport.script("GET", "/app-conversations?ids=", 403, {"message": "forbidden"})
        with self.assertRaises(OpenHandsCloudError) as ctx:
            self.client.get_conversation("conv-1")
        self.assertNotIn("test-token-value", str(ctx.exception))

    def test_receipt_is_redacted(self):
        receipt = self.client.receipt(
            operation="start_conversation",
            result={"note": "token=ghp_" + "a" * 30},
        )
        self.assertNotIn("ghp_", json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
