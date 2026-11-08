"""Tests for the optional GitHub Contents API ledger adapter."""
from __future__ import annotations

import base64
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blind_sniper_ledger import GitHubContentsLedger, GitHubLedgerError, TaskLedger  # noqa: E402


class FakeContentsAPI:
    def __init__(self):
        self.content = None
        self.sha = None
        self.put_count = 0
        self.conflict_once = False

    def __call__(self, method, url, headers, body=None):
        if method == "GET":
            if self.content is None:
                return 404, b'{"message":"Not Found"}'
            return 200, json.dumps({
                "sha": self.sha,
                "encoding": "base64",
                "content": base64.b64encode(self.content).decode("ascii"),
            }).encode()
        if method == "PUT":
            payload = json.loads(body.decode())
            expected = payload.get("sha")
            if self.conflict_once:
                self.conflict_once = False
                # Simulate a competing writer committing a valid first event.
                with tempfile.TemporaryDirectory() as tmp:
                    ledger = TaskLedger(Path(tmp) / "events.jsonl")
                    ledger.append(task_id="BS-GH-OTHER", event_type="TASK_CREATED",
                                  payload={"source": "competing-writer"},
                                  idempotency_key="other:create")
                    self.content = ledger.path.read_bytes()
                    self.sha = self._blob_sha(self.content)
                return 409, b'{"message":"sha conflict"}'
            if self.content is None and expected is not None:
                return 409, b'{"message":"unexpected sha"}'
            if self.content is not None and expected != self.sha:
                return 409, b'{"message":"sha conflict"}'
            self.content = base64.b64decode(payload["content"])
            self.sha = self._blob_sha(self.content)
            self.put_count += 1
            return 200, json.dumps({"content": {"sha": self.sha},
                                    "commit": {"sha": "c" * 40}}).encode()
        raise AssertionError(f"Unexpected method: {method}")

    @staticmethod
    def _blob_sha(content):
        header = f"blob {len(content)}\\0".encode()
        return hashlib.sha1(header + content).hexdigest()


class GitHubContentsLedgerTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeContentsAPI()
        self.ledger = GitHubContentsLedger(
            owner="example", repo="blind-sniper", path=".blind-sniper/events.jsonl",
            branch="integration", token="test-token", transport=self.api,
        )

    def test_append_creates_remote_ledger_and_returns_commit_receipt(self):
        event = self.ledger.append(
            task_id="BS-GH-001", event_type="TASK_CREATED",
            payload={"objective": "remote persistence"}, idempotency_key="one:create",
        )
        self.assertEqual(event["seq"], 1)
        self.assertEqual(event["commit_sha"], "c" * 40)
        self.assertEqual(self.api.put_count, 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_bytes(self.api.content)
            self.assertEqual(len(TaskLedger(path).events()), 1)

    def test_second_append_reloads_and_extends_remote_hash_chain(self):
        self.ledger.append(task_id="BS-GH-002", event_type="CREATED",
                           payload={}, idempotency_key="two:create")
        event = self.ledger.append(task_id="BS-GH-002", event_type="CHECKPOINT",
                                   payload={"status": "INSPECTING"}, idempotency_key="two:inspect")
        self.assertEqual(event["seq"], 2)
        self.assertEqual(self.api.put_count, 2)

    def test_idempotent_retry_does_not_create_an_extra_commit(self):
        args = dict(task_id="BS-GH-003", event_type="CREATED",
                    payload={"safe": True}, idempotency_key="three:create")
        first = self.ledger.append(**args)
        second = self.ledger.append(**args)
        self.assertEqual(first["event_hash"], second["event_hash"])
        self.assertEqual(self.api.put_count, 1)

    def test_sha_conflict_reloads_and_retries_without_losing_competing_event(self):
        self.api.conflict_once = True
        event = self.ledger.append(task_id="BS-GH-004", event_type="CREATED",
                                   payload={"writer": "this"}, idempotency_key="four:create")
        self.assertEqual(event["seq"], 2)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_bytes(self.api.content)
            rows = TaskLedger(path).events()
        self.assertEqual([row["task_id"] for row in rows], ["BS-GH-OTHER", "BS-GH-004"])

    def test_conflicting_idempotency_key_is_rejected(self):
        self.ledger.append(task_id="BS-GH-005", event_type="CREATED",
                           payload={}, idempotency_key="five:key")
        with self.assertRaises(GitHubLedgerError):
            self.ledger.append(task_id="BS-GH-005", event_type="CLOSED",
                               payload={}, idempotency_key="five:key")

    def test_corrupt_remote_hash_chain_fails_closed(self):
        self.api.content = b'{"seq":1,"task_id":"broken"}\\n'
        self.api.sha = self.api._blob_sha(self.api.content)
        with self.assertRaises(GitHubLedgerError):
            self.ledger.append(task_id="BS-GH-006", event_type="CREATED",
                               payload={}, idempotency_key="six:create")


if __name__ == "__main__":
    unittest.main()
