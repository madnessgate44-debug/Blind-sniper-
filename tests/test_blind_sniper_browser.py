from __future__ import annotations

import json
import os
import tempfile
import unittest
from subprocess import CompletedProcess
from pathlib import Path
from unittest.mock import patch

from scripts.blind_sniper_browser import BrowserAdapter, BrowserAdapterError, BrowserPolicyError, validate_url


class BrowserPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            "BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS": "127.0.0.1,example.test",
            "BLIND_SNIPER_BROWSER_BLOCKED_DOMAINS": "blocked.example.test",
            "BLIND_SNIPER_BROWSER_WRITE_APPROVED": "0",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def adapter(self, **kwargs):
        return BrowserAdapter(
            task_id="BS-TEST-001", run_id="run-001", session_id="test_session",
            state_dir=Path(self.temp.name) / "state",
            binary="missing-agent-browser", **kwargs,
        )

    def test_allowlist_and_blocklist(self):
        self.assertEqual(validate_url("http://127.0.0.1:8080/"), "127.0.0.1")
        with self.assertRaises(BrowserPolicyError):
            validate_url("https://not-allowed.example/")
        with self.assertRaises(BrowserPolicyError):
            validate_url("https://blocked.example.test/")

    def test_non_http_scheme_is_rejected(self):
        with self.assertRaises(BrowserPolicyError):
            validate_url("file:///etc/passwd")

    def test_wildcard_domain_rule_covers_subdomains(self):
        with patch.dict(os.environ, {"BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS": "*.example.test"}):
            self.assertEqual(validate_url("https://app.example.test/"), "app.example.test")
            self.assertEqual(validate_url("https://example.test/"), "example.test")

    def test_embedded_url_credentials_are_rejected(self):
        with self.assertRaises(BrowserPolicyError):
            validate_url("https://user:secret@example.test/")

    def test_mutating_action_requires_host_approval(self):
        adapter = self.adapter()
        adapter.state["current_url"] = "http://127.0.0.1/"
        with self.assertRaises(BrowserPolicyError):
            adapter.execute("click", "step-1", "#submit")

    def test_sensitive_selector_is_rejected(self):
        with patch.dict(os.environ, {"BLIND_SNIPER_BROWSER_WRITE_APPROVED": "1"}):
            adapter = self.adapter(approval_reference="CI-APPROVED")
            adapter.state["current_url"] = "http://127.0.0.1/"
            with self.assertRaises(BrowserPolicyError):
                adapter.execute("fill", "step-1", 'input[name="password"]', "secret")

    def test_session_cannot_be_reused_across_tasks(self):
        adapter = self.adapter()
        adapter.state["task_id"] = "OTHER-TASK"
        adapter._save_state()
        with self.assertRaises(BrowserPolicyError):
            BrowserAdapter(
                task_id="BS-TEST-001", run_id="run-001", session_id="test_session",
                state_dir=Path(self.temp.name) / "state", binary="missing-agent-browser",
            )

    def test_duplicate_step_receipt_is_rejected(self):
        adapter = self.adapter()
        adapter.receipt_file.parent.mkdir(parents=True, exist_ok=True)
        adapter.receipt_file.write_text(json.dumps({"step_id": "step-1"}) + "\n", encoding="utf-8")
        with self.assertRaises(BrowserPolicyError):
            adapter._append_receipt({"step_id": "step-1"})

    def test_action_policy_is_deny_by_default(self):
        adapter = self.adapter()
        policy = json.loads(adapter.policy_file.read_text(encoding="utf-8"))
        self.assertEqual(policy["default"], "deny")
        self.assertNotIn("eval", policy["allow"])
        self.assertNotIn("upload", policy["allow"])
        self.assertNotIn("download", policy["allow"])

    def test_engine_command_enforces_domain_and_content_boundaries(self):
        adapter = self.adapter()
        with patch("scripts.blind_sniper_browser.subprocess.run", return_value=CompletedProcess([], 0, "{}", "")) as run:
            adapter._command("open", "http://127.0.0.1/")
        command = run.call_args.args[0]
        self.assertIn("--allowed-domains", command)
        self.assertIn("--action-policy", command)
        self.assertIn("--content-boundaries", command)
        self.assertIn("127.0.0.1,example.test", command)
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_browser_command_never_uses_shell(self):
        adapter = self.adapter()
        with self.assertRaises(BrowserAdapterError):
            adapter._command("open", "http://127.0.0.1/")


if __name__ == "__main__":
    unittest.main()
