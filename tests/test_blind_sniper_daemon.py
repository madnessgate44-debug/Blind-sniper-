"""Tests for the persistent private native worker daemon."""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from blind_sniper_agent_runtime import _canonical_digest
from blind_sniper_daemon import BlindSniperDaemon, DaemonError, PrivateTaskStore, host_execution_policy_from_env
from blind_sniper_ledger import TaskLedger
from blind_sniper_model_worker import ModelWorker
from blind_sniper_tool_runtime import NativeToolRuntime
from blind_sniper_worker import DurableQueue


class PrivateNativeDaemonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.workspace = base / "repo"
        self.workspace.mkdir(mode=0o700)
        self.state = base / "private-state"
        self.state.mkdir(mode=0o700)
        self.store = PrivateTaskStore(self.state, workspace_root=self.workspace)
        self.queue = DurableQueue(TaskLedger(self.store.ledger_path))
        self.tool_runtime = NativeToolRuntime(self.queue, workspace_root=self.workspace)
        self.invocations = 0

        def invoker(*, spec, task, timeout_seconds):
            self.invocations += 1
            return {
                "run_id": f"daemon-run-{self.invocations}",
                "output_digest": f"digest-{self.invocations}",
                "output_excerpt": "completed",
                "output_text": "private result text",
                "tool_receipts": [],
            }

        self.worker = ModelWorker(invoker, max_retries=0)
        self.daemon = BlindSniperDaemon(
            queue=self.queue, worker=self.worker, owner_id="host-worker-1",
            store=self.store, lease_seconds=120, max_tasks_per_cycle=10,
        )

    def write_task(self, task_id="DAEMON-TASK-1", payload=None):
        data = {
            "task_id": task_id,
            "agent_id": "researcher",
            "objective": "Run the private task",
            "payload": payload or {"private_note": "keep outside the public repository"},
        }
        path = self.store.task_dir / f"{task_id}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(path, 0o600)
        return data, path

    def test_local_ledger_is_created_owner_only(self):
        self.assertTrue(self.store.ledger_path.exists())
        self.assertEqual(stat.S_IMODE(self.store.ledger_path.stat().st_mode), 0o600)

    def test_private_task_is_executed_once_and_receipts_stay_private(self):
        data, _ = self.write_task()
        first = self.daemon.run_once()
        self.assertEqual(first["status"], "HEALTHY")
        self.assertEqual(first["counts"]["completed"], 1)
        self.assertEqual(self.invocations, 1)
        self.assertEqual(self.queue.status(data["task_id"])["status"], "COMPLETED")
        receipts = list(self.store.receipt_dir.glob("*.json"))
        self.assertEqual(len(receipts), 1)
        self.assertEqual(stat.S_IMODE(receipts[0].stat().st_mode), 0o600)
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertEqual(receipt["output_text"], "private result text")
        outbox = self.store.notification_path.read_text(encoding="utf-8")
        self.assertIn("task.completed", outbox)
        self.assertIn("digest-1", outbox)
        self.assertNotIn("private_note", outbox)
        self.assertNotIn("private result text", outbox)
        health = json.loads(self.store.health_path.read_text(encoding="utf-8"))
        self.assertEqual(stat.S_IMODE(self.store.health_path.stat().st_mode), 0o600)
        self.assertNotIn("private_note", json.dumps(health))

        second = self.daemon.run_once()
        self.assertEqual(second["counts"]["skipped"], 1)
        self.assertEqual(self.invocations, 1)
        self.assertEqual(len(self.store.notification_path.read_text(encoding="utf-8").splitlines()), 1)

    def test_daemon_recovers_a_stale_lease_before_dispatching_task(self):
        data, _ = self.write_task("DAEMON-STALE-1")
        envelope = {
            "task_id": data["task_id"], "agent_id": data["agent_id"],
            "objective": data["objective"], "payload": data["payload"],
            "permission_profile": "read_only", "tool_allowlist": [],
            "allowed_paths": [], "browser_approval_reference": "",
        }
        old = datetime.now(timezone.utc) - timedelta(minutes=10)
        self.queue.enqueue(
            task_id=data["task_id"], kind="native_model_agent",
            payload_digest=_canonical_digest(envelope), now=old,
        )
        self.queue.claim(
            task_id=data["task_id"], owner_id="dead-worker", lease_seconds=60, now=old,
        )
        health = self.daemon.run_once()
        self.assertEqual(health["counts"]["recovered_stale_leases"], 1)
        self.assertEqual(health["counts"]["completed"], 1, health)
        self.assertEqual(self.queue.status(data["task_id"])["status"], "COMPLETED")

    def test_notification_outbox_reconciles_from_private_receipts(self):
        receipt = {
            "task_id": "DAEMON-RECON-1", "run_id": "reconcile-run",
            "queue_status": "COMPLETED", "output_digest": "receipt-digest",
            "output_text": "private content that must not enter outbox",
        }
        self.store.write_receipt("DAEMON-RECON-1", receipt)
        repaired = self.store.reconcile_notifications()
        self.assertEqual(repaired, 1)
        outbox = self.store.notification_path.read_text(encoding="utf-8")
        self.assertIn("receipt-digest", outbox)
        self.assertIn("DAEMON-RECON-1", outbox)
        self.assertNotIn("private content", outbox)
        self.assertEqual(self.store.reconcile_notifications(), 0)

    def test_private_state_must_be_outside_workspace_and_owner_only(self):
        with self.assertRaisesRegex(DaemonError, "outside the public repository"):
            PrivateTaskStore(self.workspace / "private", workspace_root=self.workspace)
        public_state = self.state / "too-open"
        public_state.mkdir(mode=0o755)
        os.chmod(public_state, 0o755)
        with self.assertRaisesRegex(DaemonError, "owner-only"):
            PrivateTaskStore(public_state, workspace_root=self.workspace)

    def test_task_file_cannot_grant_itself_tools_or_permissions(self):
        data, path = self.write_task("DAEMON-PRIV-ESCALATION")
        data["permission_profile"] = "workspace_write"
        data["tool_allowlist"] = ["repo.write_file"]
        data["allowed_paths"] = ["README.md"]
        data["browser_approval_reference"] = "task-invented-approval"
        path.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(path, 0o600)
        with self.assertRaisesRegex(DaemonError, "unsupported fields"):
            self.store.read_task(path)

    def test_daemon_uses_only_host_supplied_execution_policy(self):
        policy = {
            "permission_profile": "read_only",
            "tool_allowlist": ("repo.read_file",),
            "allowed_paths": ("README.md",),
            "browser_approval_reference": "",
        }
        daemon = BlindSniperDaemon(
            queue=self.queue, worker=self.worker, owner_id="host-worker-policy",
            store=self.store, host_policy=policy,
        )
        data, _ = self.write_task("DAEMON-HOST-POLICY")
        health = daemon.run_once()
        self.assertEqual(health["counts"]["completed"], 1, health)
        self.assertEqual(self.invocations, 1)
        self.assertEqual(self.queue.status(data["task_id"])["status"], "COMPLETED")

    def test_unregistered_agent_identity_is_rejected_before_invocation(self):
        daemon = BlindSniperDaemon(
            queue=self.queue, worker=self.worker, owner_id="host-worker-roster",
            store=self.store, allowed_agent_ids=frozenset({"researcher"}),
        )
        self.write_task("DAEMON-UNKNOWN-AGENT")
        path = self.store.task_dir / "DAEMON-UNKNOWN-AGENT.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["agent_id"] = "invented-agent"
        path.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(path, 0o600)
        health = daemon.run_once()
        self.assertEqual(health["status"], "DEGRADED")
        self.assertEqual(health["counts"]["errors"], 1)
        self.assertEqual(self.invocations, 0)

    def test_host_policy_rejects_unapproved_browser_mutations(self):
        policy = {
            "permission_profile": "workspace_write",
            "tool_allowlist": ("browser.click",),
            "allowed_paths": ("README.md",),
            "browser_approval_reference": "not-enough",
        }
        with self.assertRaisesRegex(DaemonError, "Host execution policy is invalid"):
            BlindSniperDaemon(
                queue=self.queue, worker=self.worker, owner_id="host-worker-browser",
                store=self.store, host_policy=policy,
            )

    def test_environment_policy_defaults_to_read_only_and_no_tools(self):
        with patch.dict(os.environ, {}, clear=True):
            policy = host_execution_policy_from_env()
        self.assertEqual(policy["permission_profile"], "read_only")
        self.assertEqual(policy["tool_allowlist"], ())
        self.assertEqual(policy["allowed_paths"], ())

    def test_task_file_requires_owner_only_permissions(self):
        _, path = self.write_task("DAEMON-OPEN-FILE")
        os.chmod(path, 0o644)
        with self.assertRaisesRegex(DaemonError, "owner-only"):
            self.store.read_task(path)

    def test_task_file_name_must_match_task_id_and_unknown_fields_are_rejected(self):
        data, path = self.write_task("DAEMON-NAME-1")
        data.pop("permission_profile", None)
        data.pop("tool_allowlist", None)
        data.pop("allowed_paths", None)
        data.pop("browser_approval_reference", None)
        path.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(path, 0o600)
        mismatch = self.store.task_dir / "OTHER-NAME.json"
        mismatch.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(mismatch, 0o600)
        with self.assertRaisesRegex(DaemonError, "filename"):
            self.store.read_task(mismatch)
        data["unexpected"] = "not allowed"
        path.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(path, 0o600)
        with self.assertRaisesRegex(DaemonError, "unsupported fields"):
            self.store.read_task(path)

    def test_stop_event_prevents_unattended_loop_from_starting(self):
        stop = threading.Event()
        stop.set()
        self.daemon.run_forever(poll_interval=1, stop_event=stop)
        self.assertEqual(self.invocations, 0)


if __name__ == "__main__":
    unittest.main()
