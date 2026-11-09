"""Contract tests for the durable allowlisted executor workflow.

CI installs no third-party Python packages, so these assertions read the workflow
file as text and check its security-relevant shape rather than parsing YAML.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "blind-sniper-executor.yml"


class ExecutorWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_exists(self):
        self.assertTrue(WORKFLOW.is_file())

    def test_trigger_is_workflow_dispatch_only(self):
        self.assertIn("workflow_dispatch:", self.text)
        # A durable executor must not run on push/pull_request.
        self.assertNotIn("\n  push:", self.text)
        self.assertNotIn("\n  pull_request:", self.text)
        self.assertNotIn("pull_request_target", self.text)

    def test_inputs_declared(self):
        self.assertIn("task_id:", self.text)
        self.assertIn("command:", self.text)
        self.assertIn("type: choice", self.text)

    def test_command_choices_are_allowlisted(self):
        for value in ("validate-runtime", "run-tests"):
            self.assertIn(value, self.text)

    def test_only_default_token_is_referenced(self):
        referenced = set(re.findall(r"secrets\.([A-Za-z0-9_]+)", self.text))
        self.assertEqual(referenced, {"GITHUB_TOKEN"})

    def test_execute_job_is_read_only(self):
        execute = self.text.split("publish-receipt:", 1)[0]
        self.assertIn("contents: read", execute)
        self.assertNotIn("contents: write", execute)

    def test_publish_job_has_write_and_targets_receipts_branch(self):
        publish = self.text.split("publish-receipt:", 1)[1]
        self.assertIn("contents: write", publish)
        self.assertIn("receipts/main", publish)
        # Must not push to main.
        self.assertNotIn("HEAD:main", publish)

    def test_receipt_is_uploaded_and_downloaded(self):
        self.assertIn("actions/upload-artifact@v4", self.text)
        self.assertIn("actions/download-artifact@v4", self.text)
        self.assertIn("ops/receipts/", self.text)

    def test_checkout_is_read_only_and_sparse(self):
        self.assertIn("persist-credentials: false", self.text)
        self.assertIn("sparse-checkout:", self.text)

    def test_unknown_command_is_refused(self):
        self.assertIn("not in the allowlist", self.text)


if __name__ == "__main__":
    unittest.main()
