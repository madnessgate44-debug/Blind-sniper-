"""Synthetic tests for typed handoff, claim-once and ledger recovery."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blind_sniper_memory import MemoryError  # noqa: E402
from blind_sniper_memory_handoff import (  # noqa: E402
    HandoffError,
    build_handoff,
    claim_handoff,
    recover_handoff,
    recover_native_handoff,
    write_handoff,
)


def packet(**overrides):
    values = {
        "handoff_id": "handoff:test-001",
        "task_id": "BS-HANDOFF-001",
        "from_agent": "planner",
        "to_agent": "implementer",
        "created_at": "2026-11-14T12:00:00Z",
        "objective": "Continue bounded task using current ledger state.",
        "verified_state": {"status": "VERIFYING", "attempt": 2, "receipt_digest": "c" * 64},
        "open_questions": ["Confirm the failing test case."],
        "files_touched": ["scripts/blind_sniper_memory.py", "tests/test_blind_sniper_memory.py"],
        "evidence_refs": ["run:123", "receipt:BS-HANDOFF-001"],
        "next_action": "Read current task state and resume verification.",
    }
    values.update(overrides)
    return build_handoff(**values)


from blind_sniper_ledger import TaskLedger  # noqa: E402
from blind_sniper_worker import DurableQueue  # noqa: E402


class HandoffTests(unittest.TestCase):
    def test_create_claim_once_and_recover_from_authoritative_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "handoffs"
            item = packet()
            self.assertEqual(write_handoff(root, item), "CREATED")
            self.assertEqual(write_handoff(root, item), "DUPLICATE")
            self.assertEqual(claim_handoff(root, item["handoff_id"], "implementer"), "CLAIMED")
            self.assertEqual(claim_handoff(root, item["handoff_id"], "implementer"), "ALREADY_CLAIMED")
            state = {"task_id": item["task_id"], "status": "COMPLETED", "attempt": 2}
            result = recover_handoff(
                root, item["handoff_id"], "implementer",
                task_state_reader=lambda task_id: state if task_id == item["task_id"] else None,
                approved_knowledge_reader=lambda _task_id: [{"page_id": "approved-1", "status": "approved"}],
            )
            self.assertEqual(result["current_task_state"], state)
            self.assertEqual(result["task_state_source"], "native_task_ledger")
            self.assertEqual(result["approved_knowledge"][0]["page_id"], "approved-1")

    def test_native_recovery_reads_current_state_from_durable_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = DurableQueue(TaskLedger(root / "ledger.jsonl"))
            queue.enqueue(task_id="BS-HANDOFF-001", kind="test", payload_digest="d" * 64, max_attempts=2)
            item = packet()
            handoffs = root / "handoffs"
            write_handoff(handoffs, item)
            claim_handoff(handoffs, item["handoff_id"], "implementer")
            result = recover_native_handoff(
                handoffs, item["handoff_id"], "implementer", queue=queue,
            )
            self.assertEqual(result["current_task_state"]["status"], "PENDING")
            self.assertEqual(result["current_task_state"]["task_id"], item["task_id"])

    def test_other_agent_cannot_claim_or_recover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "handoffs"
            item = packet()
            write_handoff(root, item)
            with self.assertRaisesRegex(HandoffError, "assigned"):
                claim_handoff(root, item["handoff_id"], "reviewer")
            claim_handoff(root, item["handoff_id"], "implementer")
            with self.assertRaisesRegex(HandoffError, "does not own"):
                recover_handoff(root, item["handoff_id"], "reviewer", task_state_reader=lambda _id: {"status": "PENDING"})

    def test_rejects_path_traversal_and_non_owner_storage(self):
        with self.assertRaisesRegex(HandoffError, "safe repository-relative"):
            packet(files_touched=["../private.txt"])
        with tempfile.TemporaryDirectory() as tmp:
            publicish = Path(tmp) / "open"
            publicish.mkdir(mode=0o755)
            publicish.chmod(0o755)
            with self.assertRaisesRegex((HandoffError, MemoryError), "permissions|owner-only"):
                write_handoff(publicish, packet())

    def test_new_packet_cannot_claim_itself(self):
        with self.assertRaisesRegex(HandoffError, "unclaimed"):
            packet(claim_state="claimed")


if __name__ == "__main__":
    unittest.main()
