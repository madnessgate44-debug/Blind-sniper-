"""Synthetic tests for immutable deterministic knowledge proposals."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blind_sniper_memory import append_observation, build_observation  # noqa: E402
from blind_sniper_memory_knowledge import build_proposals  # noqa: E402


def observation(event, timestamp, status, attempt=0):
    return build_observation(
        observation_id=f"obs:{event}:{attempt}",
        event_type=event,
        occurred_at=timestamp,
        source="blind_sniper_daemon",
        source_ref="BS-KNOWLEDGE-TEST-001",
        project_id="blind-sniper",
        classification="private_owner",
        content={
            "task_id": "BS-KNOWLEDGE-TEST-001",
            "agent_id": "planner",
            "status": status,
            "attempt": attempt,
            "run_id": f"run-{attempt}",
            "result_digest": "a" * 64 if status == "COMPLETED" else "",
        },
    )


class KnowledgeProposalTests(unittest.TestCase):
    def test_builds_proposed_page_from_validated_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "observations.jsonl"
            append_observation(journal, observation("task_created", "2026-11-14T12:00:00Z", "PENDING"))
            append_observation(journal, observation("task_transition", "2026-11-14T12:01:00Z", "COMPLETED", 1))
            knowledge = root / "knowledge"
            result = build_proposals(journal, knowledge)
            self.assertEqual(result, {"created": 1, "duplicates": 0, "tasks_seen": 1})
            page = next(knowledge.glob("*.md"))
            self.assertEqual(page.stat().st_mode & 0o777, 0o600)
            text = page.read_text(encoding="utf-8")
            metadata = json.loads(text.splitlines()[1])
            self.assertEqual(metadata["status"], "proposed")
            self.assertEqual(len(metadata["source_observation_ids"]), 2)
            self.assertIn("Approval required", text)
            self.assertNotIn("objective", text)

    def test_conflicting_status_evidence_is_preserved_without_auto_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "observations.jsonl"
            append_observation(journal, observation("task_transition", "2026-11-14T12:00:00Z", "COMPLETED", 1))
            append_observation(journal, observation("task_transition", "2026-11-14T12:00:00Z", "FAILED", 2))
            knowledge = root / "knowledge"
            self.assertEqual(build_proposals(journal, knowledge)["created"], 1)
            page = next(knowledge.glob("*.md"))
            metadata = json.loads(page.read_text(encoding="utf-8").splitlines()[1])
            body = page.read_text(encoding="utf-8")
            self.assertEqual(metadata["status"], "proposed")
            self.assertEqual(len(metadata["source_observation_ids"]), 2)
            self.assertIn("COMPLETED", body)
            self.assertIn("FAILED", body)
            self.assertIn("Approval required", body)

    def test_duplicate_run_does_not_overwrite_or_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "observations.jsonl"
            append_observation(journal, observation("task_created", "2026-11-14T12:00:00Z", "PENDING"))
            knowledge = root / "knowledge"
            self.assertEqual(build_proposals(journal, knowledge)["created"], 1)
            page = next(knowledge.glob("*.md"))
            before = page.read_bytes()
            self.assertEqual(build_proposals(journal, knowledge)["duplicates"], 1)
            self.assertEqual(page.read_bytes(), before)

    def test_new_evidence_creates_immutable_superseding_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "observations.jsonl"
            append_observation(journal, observation("task_created", "2026-11-14T12:00:00Z", "PENDING"))
            knowledge = root / "knowledge"
            build_proposals(journal, knowledge)
            append_observation(journal, observation("task_transition", "2026-11-14T12:01:00Z", "COMPLETED", 1))
            self.assertEqual(build_proposals(journal, knowledge)["created"], 1)
            pages = sorted(knowledge.glob("*.md"))
            self.assertEqual(len(pages), 2)
            metadata = [json.loads(page.read_text(encoding="utf-8").splitlines()[1]) for page in pages]
            latest = next(item for item in metadata if item["supersedes"])
            self.assertEqual(latest["status"], "proposed")
            self.assertEqual(len(latest["supersedes"]), 1)
            self.assertTrue(all("proposed" in p.read_text(encoding="utf-8") for p in pages))


if __name__ == "__main__":
    unittest.main()
