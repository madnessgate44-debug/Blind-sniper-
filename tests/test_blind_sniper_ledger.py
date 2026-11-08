"""Tests for Blind Sniper's native append-only task ledger."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blind_sniper_ledger import LedgerError, TaskLedger  # noqa: E402


class TaskLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = TaskLedger(Path(self.temp.name) / "state" / "events.jsonl")

    def tearDown(self):
        self.temp.cleanup()

    def test_append_and_replay_survive_new_instance(self):
        first = self.ledger.append(
            task_id="BS-LEDGER-001", event_type="TASK_CREATED",
            payload={"objective": "test persistence"}, idempotency_key="create-001",
        )
        recovered = TaskLedger(self.ledger.path).task_history("BS-LEDGER-001")
        self.assertEqual(recovered["event_count"], 1)
        self.assertEqual(recovered["last_event"]["event_hash"], first["event_hash"])

    def test_idempotent_replay_does_not_duplicate_event(self):
        args = dict(task_id="BS-LEDGER-002", event_type="CHECKPOINT",
                    payload={"status": "EXECUTING"}, idempotency_key="checkpoint-002")
        first = self.ledger.append(**args)
        second = self.ledger.append(**args)
        self.assertEqual(first, second)
        self.assertEqual(len(self.ledger.events()), 1)

    def test_idempotency_key_cannot_be_reused_for_different_content(self):
        self.ledger.append(task_id="BS-LEDGER-003", event_type="CREATED",
                           payload={}, idempotency_key="same-key")
        with self.assertRaisesRegex(LedgerError, "different event content"):
            self.ledger.append(task_id="BS-LEDGER-003", event_type="CLOSED",
                               payload={}, idempotency_key="same-key")

    def test_hash_chain_detects_tampering(self):
        self.ledger.append(task_id="BS-LEDGER-004", event_type="CREATED",
                           payload={"safe": True}, idempotency_key="tamper-1")
        raw = self.ledger.path.read_text(encoding="utf-8").replace('"safe": true', '"safe": false')
        self.ledger.path.write_text(raw, encoding="utf-8")
        with self.assertRaisesRegex(LedgerError, "hash mismatch"):
            self.ledger.events()

    def test_unknown_task_has_no_recovery_snapshot(self):
        with self.assertRaisesRegex(LedgerError, "Unknown task_id"):
            self.ledger.task_history("missing")


if __name__ == "__main__":
    unittest.main()
