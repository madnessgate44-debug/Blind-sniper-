"""Contract tests for the durable-worker workflow shape.

CI installs no third-party Python packages, so these assertions read the
workflow file as text. They lock in the safety-relevant properties: no schedule
trigger, manual-only execution, an activation gate, least-privilege permissions
and no credentials echoed into the log.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "blind-sniper-worker.yml"


class WorkerWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_exists(self):
        self.assertTrue(WORKFLOW.is_file())

    def test_no_schedule_or_cron_trigger(self):
        # A schedule may only be enabled once prerequisites are genuinely met.
        self.assertNotIn("\n  schedule:", self.text)
        self.assertNotIn("cron:", self.text)

    def test_manual_dispatch_only(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("\n  push:", self.text)
        self.assertNotIn("\n  pull_request:", self.text)
        self.assertNotIn("pull_request_target", self.text)

    def test_worker_pass_is_gated_on_opt_in_variable(self):
        self.assertIn("BLIND_SNIPER_AUTONOMY_ENABLED", self.text)
        self.assertIn("check-activation-only", self.text)

    def test_permissions_are_read_only(self):
        self.assertIn("contents: read", self.text)
        self.assertNotIn("contents: write", self.text)

    def test_no_raw_secret_value_is_printed(self):
        # Secrets are passed via env and never echoed.
        self.assertNotIn("echo $", self.text)
        referenced = set(re.findall(r"secrets\.([A-Za-z0-9_]+)", self.text))
        self.assertTrue(referenced.issubset({"BLIND_SNIPER_LEDGER_TOKEN", "OPENHANDS_CLOUD_API_KEY"}))


if __name__ == "__main__":
    unittest.main()
