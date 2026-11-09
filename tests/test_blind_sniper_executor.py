"""Tests for the bounded allowlisted CI verification executor."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_executor as executor  # noqa: E402
import blind_sniper_runtime as runtime  # noqa: E402


class BoundedExecutorPlanTests(unittest.TestCase):
    def test_registered_workflow_matches_only_executor_scope(self):
        plan = runtime.build_plan({
            "task_id": "BS-EXECUTOR-PLAN-001",
            "objective": "Run the bounded allowlisted verification commands",
            "workflow": executor.WORKFLOW_ID,
            "repository": "owner/repo",
        })
        self.assertEqual(plan["workflow"], "bounded-verification")
        self.assertEqual(
            [step["id"] for step in plan["steps"]],
            ["run_unit_tests", "run_runtime_validator", "await_independent_review"],
        )
        self.assertTrue(all(step["status"] == "PENDING" for step in plan["steps"]))

    def test_command_allowlist_maps_to_distinct_registered_steps(self):
        self.assertEqual(
            executor.COMMAND_STEPS,
            {
                "unit-tests": "run_unit_tests",
                "runtime-validator": "run_runtime_validator",
            },
        )
        self.assertEqual(len(set(executor.COMMAND_STEPS.values())), 2)

    def test_step_update_records_command_evidence_without_completing_review(self):
        plan = runtime.build_plan({
            "task_id": "BS-EXECUTOR-PLAN-002",
            "objective": "Run bounded verification",
            "workflow": executor.WORKFLOW_ID,
        })
        executor.update_step(
            plan, "run_unit_tests", status="PASS", exit_code=0,
            run_id="12345", commit_sha="a" * 40,
        )
        executor.update_step(
            plan, "await_independent_review",
            status="AWAITING_INDEPENDENT_REVIEW",
            reason="Requires a distinct reviewer",
        )
        steps = {step["id"]: step for step in plan["steps"]}
        self.assertEqual(steps["run_unit_tests"]["status"], "PASS")
        self.assertEqual(steps["run_unit_tests"]["exit_code"], 0)
        self.assertEqual(steps["await_independent_review"]["status"], "AWAITING_INDEPENDENT_REVIEW")

    def test_step_update_rejects_unregistered_step(self):
        plan = runtime.build_plan({
            "task_id": "BS-EXECUTOR-PLAN-003",
            "objective": "Run bounded verification",
            "workflow": executor.WORKFLOW_ID,
        })
        with self.assertRaisesRegex(RuntimeError, "exactly one planned step"):
            executor.update_step(plan, "invented-step", status="PASS")


if __name__ == "__main__":
    unittest.main()
