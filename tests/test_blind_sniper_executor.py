"""Tests for the bounded allowlisted CI verification executor."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
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


    def run_executor(self, run_id, command_results, date_error=None):
        task_file = ".blind-sniper/tasks/runtime-hardening-verification.json"
        with tempfile.TemporaryDirectory() as tmp:
            args = [
                "blind_sniper_executor.py",
                "--task-file", task_file,
                "--branch", "feat/allowlisted-executor-2026-11-09",
                "--commit", "a" * 40,
                "--run-id", str(run_id),
                "--output-dir", tmp,
            ]
            fixed_time = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)
            with patch.object(sys, "argv", args), patch.dict(os.environ, {
                "GITHUB_REF_NAME": "feat/allowlisted-executor-2026-11-09",
                "GITHUB_REPOSITORY": "owner/repo",
            }), patch.object(executor, "server_now", side_effect=date_error or [fixed_time] * 30), patch.object(
                executor.subprocess, "run", side_effect=command_results
            ) as run_mock:
                exit_code = executor.main()
            receipt_path = Path(tmp) / "receipt.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            log = (Path(tmp) / "executor.log").read_text(encoding="utf-8") if (Path(tmp) / "executor.log").exists() else ""
            return exit_code, receipt, log, run_mock.call_count

    def test_executor_success_writes_correlated_step_receipts_and_exact_log_ranges(self):
        exit_code, receipt, log, calls = self.run_executor("123456", [
            subprocess.CompletedProcess([], 0, "unit tests pass\n", ""),
            subprocess.CompletedProcess([], 0, "runtime validator pass\n", ""),
        ])
        self.assertEqual(exit_code, 0)
        self.assertEqual(receipt["status"], "REVIEWING")
        self.assertEqual([step["status"] for step in receipt["steps"]],
                         ["PASS", "PASS", "AWAITING_INDEPENDENT_REVIEW"])
        self.assertEqual(receipt["review_status"], "AWAITING_INDEPENDENT_REVIEW")
        self.assertEqual(receipt["cross_run_exclusion"], False)
        self.assertEqual(receipt["cross_run_deduplication"], False)
        lines = log.splitlines()
        first, second = receipt["commands"]
        self.assertEqual(lines[first["log_start_line"] - 1], "COMMAND 1: unit-tests")
        self.assertTrue(lines[first["log_end_line"] - 1].startswith("EXIT_CODE: 0"))
        self.assertEqual(lines[second["log_start_line"] - 1], "COMMAND 2: runtime-validator")
        self.assertTrue(lines[second["log_end_line"] - 1].startswith("EXIT_CODE: 0"))
        self.assertLess(first["log_end_line"], second["log_start_line"])
        self.assertEqual(calls, 2)

    def test_first_command_failure_blocks_second_step(self):
        exit_code, receipt, _, calls = self.run_executor("123457", [
            subprocess.CompletedProcess([], 7, "first failed\n", ""),
        ])
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "FAILED")
        self.assertEqual([step["status"] for step in receipt["steps"]],
                         ["FAIL", "BLOCKED", "AWAITING_INDEPENDENT_REVIEW"])
        self.assertEqual(calls, 1)

    def test_second_command_failure_preserves_first_pass_and_fails_task(self):
        exit_code, receipt, _, calls = self.run_executor("123458", [
            subprocess.CompletedProcess([], 0, "first pass\n", ""),
            subprocess.CompletedProcess([], 2, "second failed\n", ""),
        ])
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "FAILED")
        self.assertEqual([step["status"] for step in receipt["steps"]],
                         ["PASS", "FAIL", "AWAITING_INDEPENDENT_REVIEW"])
        self.assertEqual(calls, 2)

    def test_timeout_is_a_terminal_step_receipt_and_blocks_following_command(self):
        timeout = subprocess.TimeoutExpired(["python"], 600, output="partial\n")
        exit_code, receipt, log, calls = self.run_executor("123459", [timeout])
        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["commands"][0]["status"], "TIMED_OUT")
        self.assertIn("TIMEOUT after 600 seconds", log)
        self.assertEqual(receipt["steps"][1]["status"], "BLOCKED")
        self.assertEqual(calls, 1)

    def test_missing_server_date_fails_closed_before_execution(self):
        exit_code, receipt, _, calls = self.run_executor(
            "123460", [],
            date_error=RuntimeError("GitHub response Date header missing; refusing to use runner clock"),
        )
        self.assertEqual(exit_code, 2)
        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("Date header missing", receipt["error"])
        self.assertEqual(calls, 0)

    def test_reused_task_id_in_a_later_run_is_not_claimed_as_cross_run_deduplicated(self):
        results = [
            subprocess.CompletedProcess([], 0, "pass\n", ""),
            subprocess.CompletedProcess([], 0, "pass\n", ""),
        ]
        first = self.run_executor("123461", results)
        second = self.run_executor("123462", results)
        self.assertEqual(first[1]["task_id"], second[1]["task_id"])
        self.assertEqual(first[1]["status"], "REVIEWING")
        self.assertEqual(second[1]["status"], "REVIEWING")
        self.assertFalse(second[1]["cross_run_deduplication"])


    def test_invalid_server_date_is_rejected_without_falling_back_to_runner_clock(self):
        class Response:
            headers = {"Date": "not-a-valid-http-date"}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        with patch.object(executor, "urlopen", return_value=Response()):
            with self.assertRaises((TypeError, ValueError)):
                executor.server_now("owner/repo")

    def test_receipt_finalization_failure_raises_instead_of_returning_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = [
                "blind_sniper_executor.py",
                "--task-file", ".blind-sniper/tasks/runtime-hardening-verification.json",
                "--branch", "feat/allowlisted-executor-2026-11-09",
                "--commit", "a" * 40,
                "--run-id", "123463",
                "--output-dir", tmp,
            ]
            fixed_time = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)
            with patch.object(sys, "argv", args), patch.dict(os.environ, {
                "GITHUB_REF_NAME": "feat/allowlisted-executor-2026-11-09",
                "GITHUB_REPOSITORY": "owner/repo",
            }), patch.object(executor, "server_now", side_effect=[fixed_time] * 30), patch.object(
                executor.subprocess, "run", side_effect=[
                    subprocess.CompletedProcess([], 0, "pass\n", ""),
                    subprocess.CompletedProcess([], 0, "pass\n", ""),
                ]
            ), patch.object(Path, "write_text", side_effect=OSError("simulated receipt finalization failure")):
                with self.assertRaisesRegex(OSError, "receipt finalization failure"):
                    executor.main()

    def test_workflow_fails_if_receipt_artifact_is_missing(self):
        workflow = (ROOT / ".github" / "workflows" / "blind-sniper-allowlisted-executor.yml").read_text(encoding="utf-8")
        self.assertIn("if: always()", workflow)
        self.assertIn("if-no-files-found: error", workflow)

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
