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
        self.assertTrue(all(agent["contract_path"] for agent in plan["selected_agents"]))
        self.assertTrue(all((ROOT / agent["contract_path"]).is_file() for agent in plan["selected_agents"]))
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
            "requested_actions": ["production_deploy"],
        })
        self.assertEqual(plan["approval"]["pending_actions"], ["production_deploy"])
        state = runtime.create_task_state(plan)
        for target in ("INSPECTING", "SPECIFIED", "PLANNED"):
            state = runtime.transition_task(state, target)
        with self.assertRaisesRegex(runtime.RuntimeErrorBase, "Owner approval is pending"):
            runtime.transition_task(state, "EXECUTING")
        state = runtime.transition_task(state, "EXECUTING", approval_records=[{
            "action": "production_deploy",
            "approver": "Ahmed",
            "verbatim_words": "Ahmed: I approve production_deploy for BS-TEST-005",
            "timestamp": "2026-11-08T13:00:00Z",
        }])
        self.assertEqual(state["plan"]["approval"]["pending_actions"], [])

    def test_task_envelope_cannot_self_approve_high_risk_action(self):
        plan = runtime.build_plan({
            "task_id": "BS-TEST-009",
            "objective": "Owner-directed bounded task",
            "workflow": "task-control-loop",
            "requested_actions": ["production_deploy"],
            "owner_approval": {"approved_actions": ["production_deploy"]},
        })
        self.assertEqual(plan["approval"]["approved_actions"], [])
        self.assertEqual(plan["approval"]["pending_actions"], ["production_deploy"])
        state = runtime.create_task_state(plan)
        for target in ("INSPECTING", "SPECIFIED", "PLANNED"):
            state = runtime.transition_task(state, target)
        with self.assertRaisesRegex(runtime.RuntimeErrorBase, "Owner approval is pending"):
            runtime.transition_task(state, "EXECUTING")

    def test_merge_requires_explicit_owner_approval(self):
        plan = runtime.build_plan({
            "task_id": "BS-TEST-010",
            "objective": "Integrate verified repository changes",
            "workflow": "task-control-loop",
            "requested_actions": ["merge"],
        })
        self.assertEqual(plan["approval"]["pending_actions"], ["merge"])

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
        with self.assertRaisesRegex(runtime.RuntimeErrorBase, "reviewer distinct"):
            runtime.transition_task(state, "CLOSED")
        state = runtime.transition_task(state, "CLOSED", {
            "review_verdict": "PASS",
            "reviewer_id": "independent-reviewer",
            "task_id": "BS-TEST-006",
            "commit_sha": "b" * 40,
            "ci_run_id": "42481330782",
        })
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


    def test_unclassified_and_merge_actions_are_high_risk_and_task_cannot_override_host_policy(self):
        plan = runtime.build_plan({
            "task_id": "BS-SEC-001",
            "objective": "Perform requested repository work",
            "workflow": "task-control-loop",
            "profile": "unrestricted",
            "requested_actions": ["merge_to_main", "force_push", "unknown_action"],
            "forbidden_actions": [],
        })
        self.assertEqual(plan["profile"], "blind-sniper")
        self.assertEqual(plan["approval"]["pending_actions"], ["force_push", "merge_to_main", "unknown_action"])
        self.assertTrue(plan["constraints"]["forbidden_actions"])

    def test_owner_approval_requires_action_verbatim_words_and_timestamp(self):
        plan = runtime.build_plan({
            "task_id": "BS-SEC-002",
            "objective": "Perform protected action",
            "workflow": "task-control-loop",
            "requested_actions": ["merge_to_main"],
        })
        state = runtime.create_task_state(plan)
        for target in ("INSPECTING", "SPECIFIED", "PLANNED"):
            state = runtime.transition_task(state, target)
        with self.assertRaises(runtime.RuntimeErrorBase):
            runtime.transition_task(state, "EXECUTING", approved_actions=["merge_to_main"])
        record = {
            "action": "merge_to_main",
            "approver": "Ahmed",
            "verbatim_words": "Ahmed: I approve merge_to_main for BS-SEC-002",
            "timestamp": "2026-11-08T13:00:00Z",
        }
        state = runtime.transition_task(state, "EXECUTING", approval_records=[record])
        self.assertEqual(state["plan"]["approval"]["pending_actions"], [])

    def test_closure_requires_correlated_independent_reviewer_receipt(self):
        plan = runtime.build_plan({
            "task_id": "BS-SEC-003",
            "objective": "Research and verify a technical question",
            "workflow": "task-control-loop",
        })
        state = runtime.create_task_state(plan)
        state["implementer_id"] = "engineer"
        for target in ("INSPECTING", "SPECIFIED", "PLANNED", "EXECUTING", "VERIFYING", "REVIEWING"):
            evidence = {"verification_passed": True} if target == "REVIEWING" else {}
            state = runtime.transition_task(state, target, evidence)
        with self.assertRaises(runtime.RuntimeErrorBase):
            runtime.transition_task(state, "CLOSED", {"review_verdict": "PASS"})
        receipt = {
            "review_verdict": "PASS",
            "task_id": "BS-SEC-003",
            "reviewer_id": "independent-reviewer",
            "commit_sha": "a" * 40,
            "ci_run_id": "42481330782",
        }
        state = runtime.transition_task(state, "CLOSED", receipt)
        self.assertEqual(state["status"], "CLOSED")

    def test_routing_prioritizes_explicit_action_intent_over_generic_review_words(self):
        plan = runtime.build_plan({
            "task_id": "BS-ROUTE-001",
            "objective": "Research merge strategies and compare primary sources",
        })
        self.assertEqual(plan["workflow"], "research-and-synthesis")

    def test_bugfix_after_code_review_routes_to_engineering_not_review_only(self):
        plan = runtime.build_plan({
            "task_id": "BS-ROUTE-002",
            "objective": "Fix the bug from code review",
        })
        self.assertEqual(plan["workflow"], "inspect-plan-implement-verify")


    def test_runtime_plan_cli_persists_created_state_to_native_ledger(self):
        import json
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp) / "task.json"
            state = Path(tmp) / "state.json"
            ledger = Path(tmp) / "events.jsonl"
            task.write_text(json.dumps({
                "task_id": "BS-LIFECYCLE-001",
                "objective": "Research durable task recovery",
            }), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "blind_sniper_runtime.py"),
                "plan", "--task-file", str(task), "--output", str(state),
                "--ledger", str(ledger),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            history = runtime.TaskLedger(ledger).task_history("BS-LIFECYCLE-001")
            self.assertEqual(history["event_count"], 1)
            self.assertEqual(history["last_event"]["event_type"], "TASK_CREATED")
            self.assertEqual(history["last_event"]["payload"]["state"]["status"], "REQUESTED")

    def test_transition_cli_appends_every_state_and_recovery_reconstructs_latest(self):
        import json
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp) / "task.json"
            state = Path(tmp) / "state.json"
            ledger = Path(tmp) / "events.jsonl"
            recovered = Path(tmp) / "recovered.json"
            task.write_text(json.dumps({
                "task_id": "BS-LIFECYCLE-002",
                "objective": "Research durable task recovery",
            }), encoding="utf-8")
            command = [sys.executable, str(ROOT / "scripts" / "blind_sniper_runtime.py")]
            created = subprocess.run(command + [
                "plan", "--task-file", str(task), "--output", str(state), "--ledger", str(ledger),
            ], capture_output=True, text=True)
            self.assertEqual(created.returncode, 0, created.stderr)
            for target in ("INSPECTING", "SPECIFIED"):
                moved = subprocess.run(command + [
                    "transition", "--state-file", str(state), "--to", target,
                    "--output", str(state), "--ledger", str(ledger),
                ], capture_output=True, text=True)
                self.assertEqual(moved.returncode, 0, moved.stderr)
            state.write_text('{"task_id":"BS-LIFECYCLE-002","status":"REQUESTED"}', encoding="utf-8")
            replay = subprocess.run(command + [
                "recover", "--ledger", str(ledger), "--task-id", "BS-LIFECYCLE-002",
                "--output", str(recovered),
            ], capture_output=True, text=True)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            restored = json.loads(recovered.read_text(encoding="utf-8"))
            self.assertEqual(restored["status"], "SPECIFIED")
            self.assertEqual(len(restored["events"]), 3)
            self.assertEqual(runtime.TaskLedger(ledger).task_history("BS-LIFECYCLE-002")["event_count"], 3)

    def test_transition_cli_recovers_ledger_state_before_advancing_stale_checkpoint(self):
        import json
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp) / "task.json"
            state = Path(tmp) / "state.json"
            ledger = Path(tmp) / "events.jsonl"
            task.write_text(json.dumps({
                "task_id": "BS-LIFECYCLE-003",
                "objective": "Research stale checkpoint recovery",
            }), encoding="utf-8")
            command = [sys.executable, str(ROOT / "scripts" / "blind_sniper_runtime.py")]
            subprocess.run(command + [
                "plan", "--task-file", str(task), "--output", str(state), "--ledger", str(ledger),
            ], check=True, capture_output=True, text=True)
            for target in ("INSPECTING", "SPECIFIED"):
                subprocess.run(command + [
                    "transition", "--state-file", str(state), "--to", target,
                    "--output", str(state), "--ledger", str(ledger),
                ], check=True, capture_output=True, text=True)
            stale = json.loads(state.read_text(encoding="utf-8"))
            stale["status"] = "REQUESTED"
            state.write_text(json.dumps(stale), encoding="utf-8")
            moved = subprocess.run(command + [
                "transition", "--state-file", str(state), "--to", "PLANNED",
                "--output", str(state), "--ledger", str(ledger),
            ], capture_output=True, text=True)
            self.assertEqual(moved.returncode, 0, moved.stderr)
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["status"], "PLANNED")
            self.assertEqual(runtime.TaskLedger(ledger).task_history("BS-LIFECYCLE-003")["event_count"], 4)


    def test_host_forbidden_action_cannot_be_overridden_by_owner_approval_record(self):
        plan = runtime.build_plan({
            "task_id": "BS-SEC-004",
            "objective": "Attempt a prohibited repository operation",
            "workflow": "task-control-loop",
            "requested_actions": ["force_push"],
            "forbidden_actions": [],
        })
        self.assertIn("force_push", plan["constraints"]["forbidden_actions"])
        state = runtime.create_task_state(plan)
        for target in ("INSPECTING", "SPECIFIED", "PLANNED"):
            state = runtime.transition_task(state, target)
        approval = {
            "action": "force_push",
            "approver": "Ahmed",
            "verbatim_words": "Ahmed: I approve force_push for BS-SEC-004",
            "timestamp": "2026-11-08T15:00:00+02:00",
        }
        with self.assertRaisesRegex(runtime.RuntimeErrorBase, "host policy forbids"):
            runtime.transition_task(state, "EXECUTING", approval_records=[approval])


    def test_workflow_registry_owns_routing_rules_and_agent_selection(self):
        registries = runtime.load_registries(ROOT)
        workflows = {row["id"]: row for row in registries["workflows"]["workflows"]}
        engineering = workflows["inspect-plan-implement-verify"]
        self.assertTrue(engineering.get("routing", {}).get("keywords"))
        self.assertEqual(engineering.get("agents"), ["planner", "engineer", "qa-verifier", "reviewer"])
        plan = runtime.build_plan({
            "task_id": "BS-REGISTRY-001",
            "objective": "Fix the bug from code review",
        })
        self.assertEqual(plan["workflow"], "inspect-plan-implement-verify")
        self.assertEqual([row["id"] for row in plan["selected_agents"]],
                         engineering["agents"])

    def test_research_phrase_does_not_route_to_release_for_merge_strategy_question(self):
        registries = runtime.load_registries(ROOT)
        workflow = runtime.choose_workflow(
            {"objective": "Research merge strategies and compare primary sources"},
            registries["workflows"]["workflows"],
        )
        self.assertEqual(workflow, "research-and-synthesis")


    def test_runtime_cli_requires_active_lease_before_execution_and_supports_release(self):
        import json
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp) / "task.json"
            state = Path(tmp) / "state.json"
            ledger = Path(tmp) / "events.jsonl"
            task.write_text(json.dumps({
                "task_id": "BS-LEASE-CLI-001",
                "objective": "Research and verify a technical question",
            }), encoding="utf-8")
            command = [sys.executable, str(ROOT / "scripts" / "blind_sniper_runtime.py")]
            created = subprocess.run(command + [
                "plan", "--task-file", str(task), "--output", str(state), "--ledger", str(ledger),
            ], capture_output=True, text=True)
            self.assertEqual(created.returncode, 0, created.stderr)
            for target in ("INSPECTING", "SPECIFIED", "PLANNED"):
                moved = subprocess.run(command + [
                    "transition", "--state-file", str(state), "--to", target,
                    "--output", str(state), "--ledger", str(ledger),
                ], capture_output=True, text=True)
                self.assertEqual(moved.returncode, 0, moved.stderr)
            blocked = subprocess.run(command + [
                "transition", "--state-file", str(state), "--to", "EXECUTING",
                "--output", str(state), "--ledger", str(ledger),
            ], capture_output=True, text=True)
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("lease", blocked.stderr.lower())
            claimed = subprocess.run(command + [
                "claim", "--task-id", "BS-LEASE-CLI-001", "--owner-id", "runner-1",
                "--lease-seconds", "60", "--idempotency-key", "runner-1:claim",
                "--ledger", str(ledger),
            ], capture_output=True, text=True)
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            moved = subprocess.run(command + [
                "transition", "--state-file", str(state), "--to", "EXECUTING",
                "--output", str(state), "--ledger", str(ledger), "--lease-owner", "runner-1",
            ], capture_output=True, text=True)
            self.assertEqual(moved.returncode, 0, moved.stderr)
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["implementer_id"], "runner-1")
            released = subprocess.run(command + [
                "release", "--task-id", "BS-LEASE-CLI-001", "--owner-id", "runner-1",
                "--idempotency-key", "runner-1:release", "--ledger", str(ledger),
            ], capture_output=True, text=True)
            self.assertEqual(released.returncode, 0, released.stderr)


if __name__ == "__main__":
    unittest.main()
