"""Tests proving native daemon lifecycle capture stores metadata only."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from blind_sniper_daemon import BlindSniperDaemon  # noqa: E402


class NativeMemoryRuntimeTests(unittest.TestCase):
    def test_daemon_capture_persists_only_allowlisted_lifecycle_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            daemon = BlindSniperDaemon.__new__(BlindSniperDaemon)
            daemon.store = SimpleNamespace(memory_journal_path=Path(tmp) / "memory" / "observations.jsonl")
            daemon._memory_capture_errors = 0
            daemon._memory_capture_lock = threading.Lock()

            self.assertTrue(daemon._capture_memory(
                task_id="BS-MEMORY-TEST-001",
                event_type="task_transition",
                agent_id="planner",
                status="COMPLETED",
                attempt=2,
                run_id="run-123",
                result_digest="a" * 64,
            ))
            rows = [json.loads(line) for line in daemon.store.memory_journal_path.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            record = rows[0]
            self.assertEqual(record["source"], "blind_sniper_daemon")
            self.assertEqual(record["classification"], "private_owner")
            self.assertEqual(record["content"]["task_id"], "BS-MEMORY-TEST-001")
            self.assertEqual(record["content"]["attempt"], 2)
            self.assertNotIn("objective", record["content"])
            self.assertNotIn("payload", record["content"])
            self.assertNotIn("output", record["content"])
            self.assertEqual(daemon._memory_capture_errors, 0)

    def test_capture_failure_is_counted_without_raising(self):
        daemon = BlindSniperDaemon.__new__(BlindSniperDaemon)
        daemon.store = SimpleNamespace(memory_journal_path=Path("/proc/forbidden/memory.jsonl"))
        daemon._memory_capture_errors = 0
        daemon._memory_capture_lock = threading.Lock()
        self.assertFalse(daemon._capture_memory(
            task_id="BS-MEMORY-TEST-002",
            event_type="task_created",
            agent_id="planner",
            status="PENDING",
        ))
        self.assertEqual(daemon._memory_capture_errors, 1)


if __name__ == "__main__":
    unittest.main()
