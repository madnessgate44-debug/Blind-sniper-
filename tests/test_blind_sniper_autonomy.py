"""Tests for the continuous-autonomy runner and its activation gate.

Deterministic: uses the real local ledger, no network, no background process.
Proves the activation gate refuses to enable a schedule without prerequisites,
that one bounded pass recovers stale leases without claiming pending tasks, and that
a digest/health receipt is produced.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import blind_sniper_autonomy as autonomy  # noqa: E402
from blind_sniper_ledger import TaskLedger  # noqa: E402
from blind_sniper_worker import DurableQueue  # noqa: E402

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class ActivationGateTests(unittest.TestCase):
    def test_schedule_blocked_without_prerequisites(self):
        env = {k: v for k, v in os.environ.items() if k not in (
            "BLIND_SNIPER_MODEL_BASE_URL", "BLIND_SNIPER_MODEL_NAME", "BLIND_SNIPER_NOTIFY_DIGEST", "GITHUB_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            check = autonomy.activation_check(
                github_ledger=True, ledger_path="/nonexistent/queue.jsonl", token_env="GITHUB_TOKEN",
            )
        self.assertFalse(check["activation_allowed"])
        self.assertFalse(check["prerequisites"]["executor_configured"])
        self.assertFalse(check["prerequisites"]["notification_route_configured"])

    def test_schedule_stays_blocked_until_native_executor_exists(self):
        with patch.dict(os.environ, {
            "BLIND_SNIPER_MODEL_BASE_URL": "https://provider.example/v1",
            "BLIND_SNIPER_MODEL_NAME": "free-model", "BLIND_SNIPER_NOTIFY_DIGEST": "configured",
        }, clear=False):
            check = autonomy.activation_check(
                github_ledger=False, ledger_path=str(Path(tempfile.gettempdir()) / "q.jsonl"),
                token_env="GITHUB_TOKEN",
            )
        self.assertTrue(check["prerequisites"]["native_model_provider_configured"])
        self.assertFalse(check["prerequisites"]["executor_configured"])
        self.assertFalse(check["prerequisites"]["notification_route_configured"])
        self.assertFalse(check["activation_allowed"])

    def test_main_refuses_unattended_run_when_blocked(self):
        env = {k: v for k, v in os.environ.items() if k not in (
            "BLIND_SNIPER_MODEL_BASE_URL", "BLIND_SNIPER_MODEL_NAME", "BLIND_SNIPER_NOTIFY_DIGEST")}
        with patch.dict(os.environ, env, clear=True):
            code = autonomy.main(["--owner-id", "runner-1", "--ledger", "/nonexistent/dir/q.jsonl"])
        self.assertEqual(code, 2)


class RunOnceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.queue = DurableQueue(TaskLedger(Path(self.tmp.name) / "queue.jsonl"))
        self.out = Path(self.tmp.name) / "out"

    def test_one_pass_recovers_stale_without_claiming_pending_tasks(self):
        self.queue.enqueue(task_id="T1", kind="k", payload_digest="d1", max_attempts=3, now=T0)
        self.queue.enqueue(task_id="T2", kind="k", payload_digest="d2", max_attempts=3, now=T0)
        # Leave T1 as a stale claim by claiming with a tiny lease at T0.
        self.queue.claim(owner_id="w0", lease_seconds=1, now=T0)

        digest = autonomy.run_once(
            self.queue, owner_id="runner-1", max_tasks=5, output_dir=self.out,
            now=T0 + timedelta(seconds=120),
        )
        self.assertTrue((self.out / "autonomy-digest.json").is_file())
        self.assertTrue((self.out / "autonomy-health.json").is_file())
        self.assertEqual(digest["kind"], "autonomy_digest")
        self.assertIn("T1", digest["recovered_stale"])
        # No executor is wired into this ephemeral runner: pending work stays untouched.
        self.assertEqual(digest["execution_status"], "BLOCKED_NO_EXECUTOR")
        self.assertEqual(digest["tasks_started"], 0)
        self.assertEqual(digest["drained"], [])
        self.assertEqual(digest["pending_count"], 1)
        self.assertEqual(self.queue.status("T2")["status"], "PENDING")
        self.assertEqual(self.queue.status("T2")["attempt"], 0)
        self.assertEqual(digest["notification_delivery_status"], "NOT_CONFIGURED")

    def test_health_receipt_is_written(self):
        self.queue.enqueue(task_id="T1", kind="k", payload_digest="d1", now=T0)
        autonomy.run_once(self.queue, owner_id="runner-1", max_tasks=1, output_dir=self.out, now=T0)
        import json
        health = json.loads((self.out / "autonomy-health.json").read_text())
        self.assertIn("counts", health)


if __name__ == "__main__":
    unittest.main()
