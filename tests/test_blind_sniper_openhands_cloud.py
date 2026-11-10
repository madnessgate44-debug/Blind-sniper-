"""Contract tests for the OpenHands Cloud V1 adapter (mock transport, no network)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_openhands_cloud as oh  # noqa: E402


class FakeOpenHandsTransport:
    """Records requests and returns canned V1 responses."""

    def __init__(self, *, cancel_status=200):
        self.requests = []
        self.cancel_status = cancel_status

    def __call__(self, method, url, headers, body=None):
        payload = json.loads(body.decode()) if body else None
        self.requests.append({"method": method, "url": url, "payload": payload,
                              "auth": headers.get("Authorization")})
        if url.endswith("/api/v1/app-conversations") and method == "POST":
            return 202, json.dumps({"id": "start-1", "status": "WORKING"}).encode()
        if "/start-tasks" in url:
            return 200, json.dumps({"items": [{"id": "start-1", "app_conversation_id": "conv-1",
                                               "status": "READY"}]}).encode()
        if "/api/v1/app-conversations?ids=" in url:
            return 200, json.dumps({"items": [{"id": "conv-1", "sandbox_status": "RUNNING",
                                               "execution_status": "running",
                                               "conversation_ui_url": "https://app.all-hands.dev/canvas/conversations/conv-1"}]}).encode()
        if "/events/search" in url:
            return 200, json.dumps({"items": [{"kind": "MessageEvent", "source": "assistant"}]}).encode()
        if "/download" in url:
            return 200, b"PK\x03\x04trajectory"
        if url.endswith("/pause") or url.endswith("/cancel"):
            return self.cancel_status, b"{}"
        return 404, b"{}"


class OpenHandsCloudTests(unittest.TestCase):
    def test_disabled_without_api_key(self):
        client = oh.OpenHandsCloudClient(api_key="", transport=FakeOpenHandsTransport())
        self.assertFalse(client.enabled)
        with self.assertRaises(oh.OpenHandsCloudError):
            client.create_conversation(initial_message="do work")

    def test_create_conversation_returns_start_task(self):
        transport = FakeOpenHandsTransport()
        client = oh.OpenHandsCloudClient(api_key="secret", transport=transport)
        result = client.create_conversation(initial_message="Investigate tests", selected_repository="o/r")
        self.assertEqual(result["start_task_id"], "start-1")
        self.assertFalse(result["idempotent_replay"])
        self.assertEqual(transport.requests[0]["auth"], "Bearer secret")
        self.assertEqual(transport.requests[0]["payload"]["selected_repository"], "o/r")

    def test_dispatch_is_idempotent_on_key(self):
        transport = FakeOpenHandsTransport()
        client = oh.OpenHandsCloudClient(api_key="secret", transport=transport)
        first = client.create_conversation(initial_message="x", idempotency_key="k1")
        second = client.create_conversation(initial_message="x", idempotency_key="k1")
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(second["idempotent_replay"])
        # Only one POST was issued.
        posts = [r for r in transport.requests if r["method"] == "POST" and r["url"].endswith("/app-conversations")]
        self.assertEqual(len(posts), 1)

    def test_poll_start_task_reaches_ready(self):
        client = oh.OpenHandsCloudClient(api_key="secret", transport=FakeOpenHandsTransport())
        record = client.wait_for_start_task("start-1", max_polls=3, sleep=lambda _s: None)
        self.assertEqual(record["status"], "READY")
        self.assertEqual(record["app_conversation_id"], "conv-1")

    def test_status_messages_and_artifacts(self):
        client = oh.OpenHandsCloudClient(api_key="secret", transport=FakeOpenHandsTransport())
        status = client.conversation_status("conv-1")
        self.assertEqual(status["execution_status"], "running")
        messages = client.conversation_messages("conv-1")
        self.assertEqual(messages["event_count"], 1)
        artifacts = client.conversation_artifacts("conv-1")
        self.assertTrue(artifacts["artifacts_available"])

    def test_cancel_supported(self):
        client = oh.OpenHandsCloudClient(api_key="secret", transport=FakeOpenHandsTransport())
        self.assertTrue(client.cancel("conv-1")["cancelled"])

    def test_cancel_reports_unsupported(self):
        client = oh.OpenHandsCloudClient(api_key="secret", transport=FakeOpenHandsTransport(cancel_status=405))
        result = client.cancel("conv-1")
        self.assertFalse(result["cancelled"])

    def test_responses_are_redacted(self):
        class Leaky(FakeOpenHandsTransport):
            def __call__(self, method, url, headers, body=None):
                return 200, json.dumps({"id": "s", "app_conversation_id": "c",
                                        "detail": "token sk-" + "a" * 24}).encode()

        client = oh.OpenHandsCloudClient(api_key="secret", transport=Leaky())
        result = client.create_conversation(initial_message="x")
        self.assertNotIn("sk-", json.dumps(result))

    def test_capabilities_reports_secret_env_and_disabled_cost(self):
        caps = oh.OpenHandsCloudClient(api_key="").capabilities()
        self.assertEqual(caps["secret_env"], "OPENHANDS_CLOUD_API_KEY")
        self.assertFalse(caps["enabled"])
        self.assertEqual(caps["cost_class"], "usage_based_unverified")

    def test_reads_secret_from_environment(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"OPENHANDS_CLOUD_API_KEY": "env-secret"}):
            client = oh.OpenHandsCloudClient(transport=FakeOpenHandsTransport())
            self.assertTrue(client.enabled)


if __name__ == "__main__":
    unittest.main()
