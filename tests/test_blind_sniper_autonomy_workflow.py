"""Contract tests for the continuous-autonomy workflow (R5).

CI installs no YAML parser, so these assertions read the workflow as text and
check the security- and honesty-relevant shape: manual dispatch only, no
schedule, read-only checkout, and no third-party secrets.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "blind-sniper-autonomy.yml"


class AutonomyWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_exists(self):
        self.assertTrue(WORKFLOW.is_file())

    def test_no_schedule_trigger_is_declared(self):
        # A schedule must not be activated until prerequisites are configured.
        self.assertNotIn("\n  schedule:", self.text)
        self.assertNotIn("cron:", self.text)

    def test_trigger_is_workflow_dispatch_only(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("\n  push:", self.text)
        self.assertNotIn("\n  pull_request:", self.text)
        self.assertNotIn("pull_request_target", self.text)

    def test_checkout_is_read_only(self):
        self.assertIn("persist-credentials: false", self.text)
        self.assertIn("contents: read", self.text)
        self.assertNotIn("contents: write", self.text)

    def test_no_secrets_are_referenced(self):
        # The acceptance workflow needs no credentials: it runs read-only tests
        # and the worker CLI over the local ledger.
        referenced = set(re.findall(r"secrets\.([A-Za-z0-9_]+)", self.text))
        self.assertEqual(referenced, set())

    def test_runs_the_new_acceptance_tests(self):
        for name in ("test_blind_sniper_queue.py", "test_blind_sniper_worker.py",
                     "test_blind_sniper_model_worker.py", "test_blind_sniper_openhands_cloud.py",
                     "test_blind_sniper_forge_mcp.py", "test_blind_sniper_autonomous_e2e.py"):
            self.assertIn(name, self.text)

    def test_worker_pass_sweeps_stale_leases(self):
        self.assertIn("--sweep-stale", self.text)


if __name__ == "__main__":
    unittest.main()
