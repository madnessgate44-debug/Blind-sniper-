"""Synthetic tests for the privacy-gated memory observation journal."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from blind_sniper_memory import (  # noqa: E402
    MemoryError,
    append_observation,
    build_observation,
)


def sample(**overrides):
    values = {
        "observation_id": "obs:test-001",
        "event_type": "task_transition",
        "occurred_at": "2026-11-14T12:00:00Z",
        "source": "blind_sniper_runtime",
        "source_ref": "task:BS-TEST-001",
        "project_id": "blind-sniper",
        "classification": "public_project",
        "content": {"from": "PLANNED", "to": "VERIFYING", "note": "synthetic fixture"},
    }
    values.update(overrides)
    return values


class MemoryObservationTests(unittest.TestCase):
    def test_builds_closed_record_with_digest(self):
        record = build_observation(**sample())
        self.assertEqual(record["schema_version"], "1.0.0")
        self.assertEqual(len(record["content_digest"]), 64)
        self.assertEqual(record["classification"], "public_project")

    def test_redacts_known_secret_patterns_before_record_creation(self):
        record = build_observation(**sample(content={"log": "token sk-" + "a" * 30}))
        self.assertNotIn("sk-", json.dumps(record["content"]))

    def test_rejects_sensitive_field_names(self):
        with self.assertRaisesRegex(MemoryError, "sensitive field"):
            build_observation(**sample(content={"nested": {"api_key": "synthetic"}}))

    def test_rejects_sensitive_classification(self):
        with self.assertRaisesRegex(MemoryError, "classification"):
            build_observation(**sample(classification="sensitive_payload"))

    def test_rejects_unknown_event_and_source(self):
        with self.assertRaisesRegex(MemoryError, "event_type"):
            build_observation(**sample(event_type="raw_transcript"))
        with self.assertRaisesRegex(MemoryError, "source"):
            build_observation(**sample(source="chatgpt_conversation"))

    def test_rejects_timezone_naive_timestamp(self):
        with self.assertRaisesRegex(MemoryError, "timezone"):
            build_observation(**sample(occurred_at="2026-11-14T12:00:00"))

    def test_rejects_oversized_content(self):
        with self.assertRaisesRegex(MemoryError, "exceeds"):
            build_observation(**sample(content={"text": "x" * 9000}))

    def test_appends_and_deduplicates_identical_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "memory.jsonl"
            record = build_observation(**sample())
            self.assertEqual(append_observation(journal, record), "APPENDED")
            self.assertEqual(append_observation(journal, record), "DUPLICATE")
            self.assertEqual(len(journal.read_text(encoding="utf-8").splitlines()), 1)
            self.assertEqual(journal.stat().st_mode & 0o777, 0o600)

    def test_rejects_id_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "memory.jsonl"
            first = build_observation(**sample())
            second = build_observation(**sample(content={"to": "CLOSED"}))
            append_observation(journal, first)
            with self.assertRaisesRegex(MemoryError, "collision"):
                append_observation(journal, second)

    def test_rejects_journal_inside_repository(self):
        repo_journal = Path(__file__).resolve().parents[1] / ".blind-sniper" / "forbidden-memory.jsonl"
        record = build_observation(**sample())
        with self.assertRaisesRegex(MemoryError, "outside the repository"):
            append_observation(repo_journal, record)


if __name__ == "__main__":
    unittest.main()
