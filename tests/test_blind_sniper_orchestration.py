"""Behavioral tests for Blind Sniper's executable orchestration engine."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blind_sniper_runtime as runtime  # noqa: E402


class OrchestrationEngineTests(unittest.TestCase):
    def test_engineering_task_routes_through_registered_profile(self):
        plan = runtime.build_plan({
            "task_id": "BS-TEST-001",
            "objective": "Implement orchestration integration and verify GitHub repository tests",
            "repository": "owner/repo",
        })
        self.assertEqual(plan["workflow"], "inspect-plan-implement-verify")
        self.assertEqual(plan["profile"], "engineering")
        self.assertEqual(plan["execution_readiness"], "PARTIAL")
        self.assertEqual(plan["next_action"], "HOST_ASSISTED_EXECUTION")
        self.assertTrue(plan["selected_agents"])
        self.assertTrue(plan["selected_skills"])
        self.assertTrue(all((ROOT / skill["path"]).is_file() for skill in plan["selected_skills"]))
        self.assertFalse(plan["constraints"]["external_execution_performed"])

    def test_research_task_routes_to_available_research_adapters(self):
        plan = runtime.build_plan({
            "task_id": "BS-TEST-002",
            "objective": "Research and compare primary sources for this question",
        })
        self.assertEqual(plan["workflow"], "research-and-synthesis")
        self.assertEqual(plan["profile"], "research")
        self.assertEqual(plan["execution_readiness"], "READY")
        self.assertEqual(plan["next_action"], "EXECUTE_WITH_HOST")

    def test_unknown_workflow_fails_closed(self):
        with self.assertRaises(runtime.RuntimeErrorBase):
            runtime.build_plan({
                "task_id": "BS-TEST-003",
                "objective": "Do work",
                "workflow": "invented-workflow",
            })

    def test_missing_task_correlation_id_is_rejected(self):
        with self.assertRaises(runtime.RuntimeErrorBase):
            runtime.build_plan({"objective": "Research a topic"})

    def test_unregistered_browser_adapter_blocks_execution(self):
        plan = runtime.build_plan({
            "task_id": "BS-TEST-004",
            "objective": "Read-only browser task",
            "workflow": "forge-browser-roundtrip",
        })
        self.assertEqual(plan["execution_readiness"], "BLOCKED")
        state = runtime.create_task_state(plan)
        for target in ("INSPECTING", "SPECIFIED", "PLANNED"):
            state = runtime.transition_task(state, target)
        with self.assertRaisesRegex(runtime.RuntimeErrorBase, "blocked or unverified"):
            runtime.transition_task(state, "EXECUTING")

    def test_high_risk_action_requires_owner_approval(self):
        plan = runtime.build_plan({
            "task_id": "BS-TEST-005",
            "objective": "Owner-directed bounded task",
            "workflow": "task-control-loop",
            "requested_actions": ["merge"],
        })
        self.assertEqual(plan["approval"]["pending_actions"], ["merge"])
        state = runtime.create_task_state(plan)
        for target in ("INSPECTING", "SPECIFIED", "PLANNED"):
            state = runtime.transition_task(state, target)
        with self.assertRaisesRegex(runtime.RuntimeErrorBase, "Owner approval is pending"):
            runtime.transition_task(state, "EXECUTING")
        state = runtime.transition_task(state, "EXECUTING", approved_actions=["merge"])
        self.assertEqual(state["plan"]["approval"]["pending_actions"], [])

    def test_release_gate_detects_missing_deploy_and_merge_capabilities(self):
        plan = runtime.build_plan({
            "task_id": "BS-TEST-008",
            "objective": "Prepare a release",
            "workflow": "release-gate",
        })
        self.assertEqual(plan["execution_readiness"], "BLOCKED")
        missing = {item["id"]: item["missing_capabilities"] for item in plan["required_adapters"]}
        self.assertIn("merge", missing["github"])
        self.assertIn("deploy", missing["vercel"])

    def test_lifecycle_requires_verification_and_review_before_close(self):
        plan = runtime.build_plan({
            "task_id": "BS-TEST-006",
            "objective": "Research a technical question",
        })
        state = runtime.create_task_state(plan)
        for target in ("INSPECTING", "SPECIFIED", "PLANNED", "EXECUTING", "VERIFYING"):
            state = runtime.transition_task(state, target)
        with self.assertRaisesRegex(runtime.RuntimeErrorBase, "verification_passed"):
            runtime.transition_task(state, "REVIEWING")
        state = runtime.transition_task(state, "REVIEWING", {"verification_passed": True})
        with self.assertRaisesRegex(runtime.RuntimeErrorBase, "independent PASS"):
            runtime.transition_task(state, "CLOSED")
        state = runtime.transition_task(state, "CLOSED", {"review_verdict": "PASS"})
        self.assertEqual(state["status"], "CLOSED")
        self.assertEqual(state["events"][-1]["to"], "CLOSED")

    def test_invalid_state_jump_is_rejected(self):
        plan = runtime.build_plan({
            "task_id": "BS-TEST-007",
            "objective": "Research a technical question",
        })
        state = runtime.create_task_state(plan)
        with self.assertRaisesRegex(runtime.RuntimeErrorBase, "Invalid transition"):
            runtime.transition_task(state, "CLOSED")


if __name__ == "__main__":
    unittest.main()
