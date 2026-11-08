"""Tests for Blind Sniper's native append-only task ledger."""
from __future__ import annotations

import json
import subprocess
import threading
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

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


    def test_task_lease_is_exclusive_until_expiry(self):
        now = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
        first = self.ledger.claim_task(
            task_id="BS-LEASE-001", owner_id="executor-a", lease_seconds=60,
            idempotency_key="lease-a", now=now,
        )
        blocked = self.ledger.claim_task(
            task_id="BS-LEASE-001", owner_id="executor-b", lease_seconds=60,
            idempotency_key="lease-b", now=now + timedelta(seconds=30),
        )
        self.assertTrue(first["claimed"])
        self.assertFalse(blocked["claimed"])
        self.assertEqual(blocked["owner_id"], "executor-a")

    def test_expired_task_lease_can_be_reclaimed(self):
        now = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
        self.ledger.claim_task(
            task_id="BS-LEASE-002", owner_id="executor-a", lease_seconds=60,
            idempotency_key="lease-a", now=now,
        )
        reclaimed = self.ledger.claim_task(
            task_id="BS-LEASE-002", owner_id="executor-b", lease_seconds=60,
            idempotency_key="lease-b", now=now + timedelta(seconds=61),
        )
        self.assertTrue(reclaimed["claimed"])
        self.assertEqual(reclaimed["owner_id"], "executor-b")

    def test_task_lease_can_be_renewed_and_released_only_by_owner(self):
        now = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
        self.ledger.claim_task(
            task_id="BS-LEASE-003", owner_id="executor-a", lease_seconds=60,
            idempotency_key="lease-a", now=now,
        )
        renewed = self.ledger.claim_task(
            task_id="BS-LEASE-003", owner_id="executor-a", lease_seconds=120,
            idempotency_key="renew-a", now=now + timedelta(seconds=30),
        )
        self.assertTrue(renewed["claimed"])
        self.assertFalse(self.ledger.release_task(
            task_id="BS-LEASE-003", owner_id="executor-b",
            idempotency_key="wrong-release", now=now + timedelta(seconds=40),
        )["released"])
        self.assertTrue(self.ledger.release_task(
            task_id="BS-LEASE-003", owner_id="executor-a",
            idempotency_key="owner-release", now=now + timedelta(seconds=40),
        )["released"])
        self.assertIsNone(self.ledger.lease_status("BS-LEASE-003", now=now + timedelta(seconds=41)))

    def test_concurrent_task_claims_have_exactly_one_winner(self):
        now = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
        barrier = threading.Barrier(2)
        results = []
        def claim(owner):
            barrier.wait()
            results.append(self.ledger.claim_task(
                task_id="BS-LEASE-004", owner_id=owner, lease_seconds=60,
                idempotency_key=f"claim-{owner}", now=now,
            ))
        threads = [threading.Thread(target=claim, args=(owner,)) for owner in ("a", "b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(1 for result in results if result["claimed"]), 1)

    def test_invalid_lease_duration_is_rejected(self):
        with self.assertRaises(LedgerError):
            self.ledger.claim_task(
                task_id="BS-LEASE-005", owner_id="executor-a", lease_seconds=0,
                idempotency_key="bad-lease",
            )


    def test_execution_transition_append_checks_lease_owner_atomically(self):
        now = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
        self.ledger.claim_task(
            task_id="BS-LEASE-006", owner_id="runner-a", lease_seconds=60,
            idempotency_key="lease-a", now=now,
        )
        payload = {"state": {"task_id": "BS-LEASE-006", "status": "EXECUTING"}}
        with self.assertRaisesRegex(LedgerError, "active lease"):
            self.ledger.append_transition_if_lease(
                task_id="BS-LEASE-006", owner_id="runner-b", payload=payload,
                idempotency_key="transition-b", now=now,
            )
        event = self.ledger.append_transition_if_lease(
            task_id="BS-LEASE-006", owner_id="runner-a", payload=payload,
            idempotency_key="transition-a", now=now,
        )
        self.assertEqual(event["event_type"], "TASK_TRANSITIONED")
        self.assertEqual(event["payload"], payload)


if __name__ == "__main__":
    unittest.main()
