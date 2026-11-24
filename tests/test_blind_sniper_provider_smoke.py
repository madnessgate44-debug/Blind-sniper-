from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_blind_sniper_provider_smoke import EXPECTED_RESPONSE, run_smoke


class FakeInvoker:
    def __init__(self, *, output_text: str = EXPECTED_RESPONSE, **kwargs):
        self.output_text = output_text
        self.kwargs = kwargs

    def __call__(self, *, spec, task, timeout_seconds):
        return {
            "run_id": "synthetic-run-001",
            "provider": "fake-test-provider",
            "model": "fake-test-model",
            "output_digest": "a" * 64,
            "output_excerpt": self.output_text,
            "output_text": self.output_text,
            "tool_receipts": [],
        }


class ProviderSmokeTests(unittest.TestCase):
    def test_missing_key_fails_closed_without_invoking_provider(self):
        output = io.StringIO()

        def forbidden_factory(**kwargs):
            self.fail("provider factory must not run without an API key")

        code = run_smoke(environ={}, invoker_factory=forbidden_factory, output=output)
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertNotIn("api_key", payload)

    def test_success_emits_metadata_only_correlated_receipt(self):
        output = io.StringIO()
        code = run_smoke(
            environ={"BLIND_SNIPER_MODEL_API_KEY": "synthetic-secret-value"},
            invoker_factory=FakeInvoker,
            output=output,
        )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["task_id"], "BS-PROVIDER-SMOKE-001")
        self.assertEqual(payload["agent_id"], "researcher")
        self.assertTrue(payload["output_match"])
        self.assertNotIn(EXPECTED_RESPONSE, output.getvalue())
        self.assertNotIn("synthetic-secret-value", output.getvalue())

    def test_unexpected_provider_output_fails_without_echoing_output(self):
        output = io.StringIO()
        code = run_smoke(
            environ={"BLIND_SNIPER_MODEL_API_KEY": "synthetic-secret-value"},
            invoker_factory=lambda **kwargs: FakeInvoker(output_text="unexpected provider text"),
            output=output,
        )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "FAIL")
        self.assertFalse(payload["output_match"])
        self.assertNotIn("unexpected provider text", output.getvalue())


    def test_keyless_requires_explicit_opt_in(self):
        output = io.StringIO()

        def forbidden_factory(**kwargs):
            self.fail("provider factory must not run when keyless opt-in is not exactly enabled")

        code = run_smoke(
            environ={"BLIND_SNIPER_PROVIDER_SMOKE_ALLOW_KEYLESS": "true"},
            invoker_factory=forbidden_factory,
            output=output,
        )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "BLOCKED")

    def test_keyless_opt_in_invokes_provider_without_key(self):
        output = io.StringIO()
        code = run_smoke(
            environ={"BLIND_SNIPER_PROVIDER_SMOKE_ALLOW_KEYLESS": "1"},
            invoker_factory=FakeInvoker,
            output=output,
        )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "PASS")
        self.assertTrue(payload["keyless"])


class ProviderWorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "blind-sniper-provider-smoke.yml"
        ).read_text(encoding="utf-8")

    def test_provider_smoke_is_manual_only(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("schedule:", self.workflow)
        self.assertNotIn("push:", self.workflow)
        self.assertNotIn("pull_request:", self.workflow)

    def test_provider_smoke_has_read_only_repository_permissions(self):
        self.assertIn("permissions:\n  contents: read", self.workflow)
        self.assertNotIn("id-token:", self.workflow)
        self.assertNotIn("contents: write", self.workflow)

    def test_provider_smoke_uses_only_the_gemini_secret_and_free_model(self):
        self.assertIn("secrets.BLIND_SNIPER_MODEL_API_KEY", self.workflow)
        self.assertIn("gemini-3.8-flash", self.workflow)
        self.assertIn("generativelanguage.googleapis.com/v1beta/openai", self.workflow)
        self.assertNotIn("OPENAI_API_KEY", self.workflow)
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", self.workflow)

    def test_provider_smoke_dispatch_inputs_default_to_gemini_and_keyless_off(self):
        self.assertIn("allow_keyless:", self.workflow)
        self.assertIn("default: false", self.workflow)
        self.assertIn('default: "gemini-3.8-flash"', self.workflow)
        self.assertIn('default: "https://generativelanguage.googleapis.com/v1beta/openai"', self.workflow)

    def test_provider_smoke_cannot_enable_autonomy_or_write_tools(self):
        self.assertNotIn("BLIND_SNIPER_AUTONOMY_ENABLED", self.workflow)
        self.assertNotIn("BLIND_SNIPER_EXECUTOR_ENABLED", self.workflow)
        self.assertNotIn("agent.handoff", self.workflow)


if __name__ == "__main__":
    unittest.main()
