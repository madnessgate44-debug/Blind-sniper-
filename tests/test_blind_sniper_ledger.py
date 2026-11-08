"""Tests for Blind Sniper's native append-only task ledger."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blind_sniper_ledger import GitHubContentsLedger, GitHubLedgerError, LedgerError, TaskLedger  # noqa: E402


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

    def test_cli_append_and_show(self):
        payload = Path(self.temp.name) / "payload.json"
        payload.write_text(json.dumps({"status": "REQUESTED"}), encoding="utf-8")
        command = [sys.executable, str(ROOT / "scripts" / "blind_sniper_ledger.py")]
        appended = subprocess.run(command + ["append", "--ledger", str(self.ledger.path),
            "--task-id", "BS-LEDGER-CLI", "--event-type", "TASK_CREATED",
            "--idempotency-key", "cli-create", "--payload-file", str(payload)],
            capture_output=True, text=True, check=False)
        self.assertEqual(appended.returncode, 0, appended.stderr)
        shown = subprocess.run(command + ["show", "--ledger", str(self.ledger.path),
            "--task-id", "BS-LEDGER-CLI"], capture_output=True, text=True, check=False)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(shown.stdout)["event_count"], 1)

    def test_unknown_task_has_no_recovery_snapshot(self):
        with self.assertRaisesRegex(LedgerError, "Unknown task_id"):
            self.ledger.task_history("missing")


    def test_github_contents_adapter_requires_explicit_credentials_and_branch(self):
        with self.assertRaises(GitHubLedgerError):
            GitHubContentsLedger(
                owner="example", repo="repo", path="events.jsonl",
                branch="main", token="",
            )


    def test_github_contents_ledger_exposes_recovery_read_interface(self):
        self.assertTrue(callable(GitHubContentsLedger.events))
        self.assertTrue(callable(GitHubContentsLedger.task_history))


    def test_github_contents_adapter_requires_private_repository_guard(self):
        self.assertTrue(callable(GitHubContentsLedger._assert_private_repository))


if __name__ == "__main__":
    unittest.main()
