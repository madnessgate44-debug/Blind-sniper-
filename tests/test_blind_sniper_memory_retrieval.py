"""Synthetic tests for approval-gated lexical retrieval."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blind_sniper_memory import append_observation, build_observation  # noqa: E402
from blind_sniper_memory_knowledge import approve_proposal, build_proposals  # noqa: E402
from blind_sniper_memory_retrieval import search_approved_pages  # noqa: E402


def sample(classification="private_owner", task_id="BS-RETRIEVAL-001"):
    return build_observation(
        observation_id="obs:retrieval:" + task_id,
        event_type="task_transition",
        occurred_at="2026-11-14T12:00:00Z",
        source="blind_sniper_daemon",
        source_ref=task_id,
        project_id="blind-sniper",
        classification=classification,
        content={
            "task_id": task_id,
            "agent_id": "planner",
            "status": "COMPLETED",
            "attempt": 1,
            "run_id": "run-1",
            "result_digest": "b" * 64,
        },
    )


class MemoryRetrievalTests(unittest.TestCase):
    def test_proposed_page_is_not_retrievable_until_explicit_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "observations.jsonl"
            append_observation(journal, sample())
            proposals = root / "proposals"
            approved = root / "approved"
            build_proposals(journal, proposals)
            query = "task lifecycle planner completed"
            self.assertEqual(search_approved_pages(query, proposals, project_id="blind-sniper")["results"], [])
            proposal = next(proposals.glob("*.md"))
            proposal_id = json.loads(proposal.read_text().splitlines()[1])["proposal_id"]
            self.assertEqual(approve_proposal(proposal, approved, reviewer="owner", expected_proposal_id=proposal_id), "APPROVED")
            result = search_approved_pages(query, approved, project_id="blind-sniper")
            self.assertEqual(len(result["results"]), 1)
            self.assertEqual(result["results"][0]["classification"], "private_owner")
            self.assertIn("BS-RETRIEVAL-001", result["context"])

    def test_rejects_stale_approval_and_wrong_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "observations.jsonl"
            append_observation(journal, sample())
            proposals, approved = root / "proposals", root / "approved"
            build_proposals(journal, proposals)
            proposal = next(proposals.glob("*.md"))
            with self.assertRaisesRegex(ValueError, "identity changed"):
                approve_proposal(proposal, approved, reviewer="owner", expected_proposal_id="stale")
            proposal_id = json.loads(proposal.read_text().splitlines()[1])["proposal_id"]
            approve_proposal(proposal, approved, reviewer="owner", expected_proposal_id=proposal_id)
            self.assertEqual(search_approved_pages("planner completed", approved, project_id="other-project")["results"], [])
            self.assertEqual(search_approved_pages("planner completed", approved, project_id="blind-sniper", scope="public")["results"], [])

    def test_context_is_byte_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "observations.jsonl"
            append_observation(journal, sample())
            proposals, approved = root / "proposals", root / "approved"
            build_proposals(journal, proposals)
            proposal = next(proposals.glob("*.md"))
            proposal_id = json.loads(proposal.read_text().splitlines()[1])["proposal_id"]
            approve_proposal(proposal, approved, reviewer="owner", expected_proposal_id=proposal_id)
            result = search_approved_pages("task lifecycle planner completed", approved, project_id="blind-sniper", max_context_bytes=256)
            self.assertLessEqual(result["context_bytes"], 256)
            self.assertTrue(result["truncated"])


if __name__ == "__main__":
    unittest.main()
