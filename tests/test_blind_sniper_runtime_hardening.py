"""Regression tests for runtime lease and approval hardening."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_runtime as runtime  # noqa: E402
from blind_sniper_ledger import TaskLedger  # noqa: E402


class RuntimeHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger_path = self.root / "events.jsonl"
        self.state_path = self.root / "state.json"
        self.output_path = self.root / "out.json"
        self.ledger = TaskLedger(self.ledger_path)
        self.plan = runtime.build_plan({
            "task_id": "BS-HARDEN-001",
            "objective": "Research a technical question",
        })

    def tearDown(self):
        self.tmp.cleanup()

    def write_state(self, status):
        state = runtime.create_task_state(self.plan)
        state["status"] = status
        state["implementer_id"] = "runner-a"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        self.ledger.append(
            task_id=state["task_id"], event_type="TASK_CREATED",
            payload={"state": state}, idempotency_key="created",
        )
        return state

    def run_transition(self, target, *extra):
        return subprocess.run([
            sys.executable, str(ROOT / "scripts" / "blind_sniper_runtime.py"),
            "transition", "--state-file", str(self.state_path), "--to", target,
            "--output", str(self.output_path), "--ledger", str(self.ledger_path),
            *extra,
        ], capture_output=True, text=True, check=False)

    def test_same_state_executing_retry_requires_live_lease(self):
        self.write_state("EXECUTING")
        old = datetime.now(timezone.utc) - timedelta(minutes=5)
        self.ledger.claim_task(
            task_id="BS-HARDEN-001", owner_id="runner-a", lease_seconds=60,
            idempotency_key="expired-lease", now=old,
        )
        result = self.run_transition("EXECUTING", "--lease-owner", "runner-a")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("active lease", result.stderr)

    def test_post_execution_transition_requires_lease_owner(self):
        self.write_state("EXECUTING")
        result = self.run_transition("VERIFYING")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("lease", result.stderr.lower())

    def test_import_rejects_non_requested_checkpoint(self):
        state = runtime.create_task_state(self.plan)
        state["status"] = "EXECUTING"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        result = self.run_transition("VERIFYING")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("import", result.stderr.lower())

    def test_approval_record_must_be_bound_to_task_and_expiry(self):
        now = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)
        base = {
            "approval_id": "approval-1",
            "task_id": "OTHER-TASK",
            "action": "production_deploy",
            "approver": "Ahmed",
            "verbatim_words": "I approve production_deploy",
            "timestamp": "2026-11-08T23:00:00Z",
            "expires_at": "2026-11-09T01:00:00Z",
        }
        with self.assertRaisesRegex(runtime.RuntimeErrorBase, "task"):
            runtime.transition_task(
                {"task_id": "BS-HARDEN-001", "status": "PLANNED", "plan": self.plan, "events": []},
                "EXECUTING", approval_records=[base], now=now,
            )
        expired = {**base, "task_id": "BS-HARDEN-001", "expires_at": "2026-11-08T23:59:00Z"}
        with self.assertRaisesRegex(runtime.RuntimeErrorBase, "expired"):
            runtime.transition_task(
                {"task_id": "BS-HARDEN-001", "status": "PLANNED", "plan": self.plan, "events": []},
                "EXECUTING", approval_records=[expired], now=now,
            )


if __name__ == "__main__":
    unittest.main()
