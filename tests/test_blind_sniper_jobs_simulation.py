"""Unit test for the scheduled-jobs end-to-end simulation.

The test runs the deterministic simulation in-process and asserts the receipt
proves the pipeline controls: deduplication, dispatch lease exclusivity, retry
with loop breaker, skip after the breaker trips, delivery, and an intact
hash-chained ledger. It never contacts a network or spawns an agent.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import simulate_blind_sniper_jobs_e2e as jobs_e2e  # noqa: E402


class JobsSimulationTest(unittest.TestCase):
    def test_simulation_passes_and_proves_pipeline_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["GITHUB_SHA"] = "a" * 40
            os.environ["GITHUB_RUN_ID"] = "424242"
            receipt = jobs_e2e.run(Path(temp) / "out")

        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["execution_mode"], "SIMULATION_ONLY")
        self.assertFalse(receipt["real_scheduler_present"])
        self.assertFalse(receipt["actual_agent_spawned"])
        self.assertEqual(receipt["external_network_calls"], 0)
        self.assertTrue(receipt["ledger_hash_chain_verified"])

        stats = receipt["stats"]
        self.assertEqual(stats["events_received"], 4)
        self.assertEqual(stats["events_deduplicated"], 1)
        self.assertEqual(stats["tasks_dispatched"], 3)
        self.assertEqual(stats["tasks_completed"], 2)
        self.assertEqual(stats["tasks_failed"], 1)
        self.assertEqual(stats["retries"], 3)
        self.assertEqual(stats["loop_breakers_tripped"], 1)
        self.assertEqual(stats["jobs_skipped"], 1)

        # A failing job's breaker trips; a healthy daily job never does.
        by_id = {job["job_id"]: job for job in receipt["jobs"]}
        self.assertTrue(by_id["job-loop"]["loop_breaker_tripped"])
        self.assertFalse(by_id["job-audit"]["loop_breaker_tripped"])
        self.assertEqual(by_id["job-audit"]["runs"], 1)
        self.assertEqual(by_id["job-loop"]["runs"], 4)
        self.assertEqual(len(receipt["deliveries"]), 2)

    def test_simulation_fails_closed_without_ci_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["GITHUB_SHA"] = ""
            os.environ["GITHUB_RUN_ID"] = ""
            with self.assertRaises(jobs_e2e.SimulationFailure):
                jobs_e2e.run(Path(temp) / "out")


if __name__ == "__main__":
    unittest.main()
