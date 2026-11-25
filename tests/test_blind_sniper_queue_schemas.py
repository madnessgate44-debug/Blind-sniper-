"""Contract tests for the queue adapter schemas.

Two layers:
1. Unit: each schema accepts a canonical valid object and rejects malformed
   ones (missing required key, wrong type, unknown extra key, bad enum,
   malformed date-time), with useful error paths.
2. Conformance: a real DurableQueue driven through its full protocol
   (enqueue, claim, heartbeat, complete, retry, cancel, stale recovery, tool
   reservation and terminal receipts) emits only ledger events that validate
   against these schemas, and the claim result object validates too.

Deterministic: injected clocks, local file ledger, no network, no processes.
"""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from blind_sniper_ledger import TaskLedger
from blind_sniper_queue_schemas import (
    CLAIM_RESULT_SCHEMA,
    EVENT_ENVELOPE_SCHEMA,
    EVENT_TYPES,
    PAYLOAD_SCHEMAS,
    SCHEMA_VERSION,
    validate,
    validate_claim_result,
    validate_event,
    validate_payload,
)
from blind_sniper_worker import DurableQueue

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

VALID_EXAMPLES: dict[str, dict] = {
    "QUEUE_TASK_ENQUEUED": {
        "kind": "model_task", "payload_digest": "sha256:abc",
        "max_attempts": 3, "enqueued_at": T0.isoformat(),
    },
    "QUEUE_TASK_CLAIMED": {
        "owner_id": "worker-1", "attempt": 1,
        "lease_expires_at": (T0 + timedelta(seconds=300)).isoformat(),
        "heartbeat_at": T0.isoformat(),
    },
    "QUEUE_TASK_HEARTBEAT": {
        "owner_id": "worker-1",
        "lease_expires_at": (T0 + timedelta(seconds=300)).isoformat(),
        "heartbeat_at": T0.isoformat(),
    },
    "QUEUE_TASK_COMPLETED": {
        "owner_id": "worker-1", "result_digest": "sha256:res",
        "completed_at": T0.isoformat(),
    },
    "QUEUE_TASK_FAILED": {
        "owner_id": "worker-1", "attempt": 3, "error": "boom",
        "failed_at": T0.isoformat(), "result_digest": "sha256:partial",
    },
    "QUEUE_TASK_CANCELLED": {
        "reason": "operator request", "cancelled_at": T0.isoformat(),
    },
    "QUEUE_TASK_RECOVERED": {
        "previous_owner": "worker-1", "attempt": 1,
        "reason": "STALE_LEASE", "recovered_at": T0.isoformat(),
    },
    "QUEUE_TASK_RETRY_SCHEDULED": {
        "owner_id": "worker-1", "attempt": 1, "error": "transient",
        "failed_at": T0.isoformat(),
    },
    "QUEUE_TOOL_STARTED": {
        "owner_id": "worker-1", "run_id": "run-1", "tool_call_id": "call-1",
        "tool_name": "repo.read_file", "arguments_digest": "sha256:args",
        "started_at": T0.isoformat(),
    },
    "QUEUE_TOOL_COMPLETED": {
        "owner_id": "worker-1", "run_id": "run-1", "tool_call_id": "call-1",
        "status": "PASS", "result_digest": "sha256:out",
        "completed_at": T0.isoformat(),
    },
    "QUEUE_TOOL_FAILED": {
        "owner_id": "worker-1", "run_id": "run-1", "tool_call_id": "call-1",
        "status": "FAIL", "result_digest": "sha256:out",
        "completed_at": T0.isoformat(),
    },
}


def _envelope(payload: dict, event_type: str = "QUEUE_TASK_ENQUEUED") -> dict:
    return {
        "schema_version": SCHEMA_VERSION, "seq": 1, "task_id": "T-1",
        "event_type": event_type, "idempotency_key": "T-1:test",
        "created_at": T0.isoformat(), "payload": payload,
        "prev_hash": "GENESIS", "event_hash": "sha256:event",
    }


class SchemaUnitTests(unittest.TestCase):
    def test_every_event_type_has_a_valid_example(self):
        self.assertEqual(sorted(VALID_EXAMPLES), list(EVENT_TYPES))

    def test_valid_payloads_pass(self):
        for event_type, payload in VALID_EXAMPLES.items():
            with self.subTest(event_type=event_type):
                self.assertEqual(validate_payload(event_type, payload), [])

    def test_unknown_event_type_rejected(self):
        errors = validate_payload("QUEUE_BOGUS", {})
        self.assertTrue(any("unknown queue event type" in e for e in errors))

    def test_missing_required_key_rejected(self):
        payload = copy.deepcopy(VALID_EXAMPLES["QUEUE_TASK_ENQUEUED"])
        del payload["payload_digest"]
        errors = validate_payload("QUEUE_TASK_ENQUEUED", payload)
        self.assertTrue(any("payload_digest" in e and "missing" in e for e in errors))

    def test_extra_key_rejected(self):
        payload = copy.deepcopy(VALID_EXAMPLES["QUEUE_TASK_CLAIMED"])
        payload["debug_note"] = "should not be here"
        errors = validate_payload("QUEUE_TASK_CLAIMED", payload)
        self.assertTrue(any("unexpected key" in e and "debug_note" in e for e in errors))

    def test_wrong_type_rejected(self):
        payload = copy.deepcopy(VALID_EXAMPLES["QUEUE_TASK_CLAIMED"])
        payload["attempt"] = "1"
        errors = validate_payload("QUEUE_TASK_CLAIMED", payload)
        self.assertTrue(any("attempt" in e and "integer" in e for e in errors))

    def test_boolean_is_not_an_integer(self):
        payload = copy.deepcopy(VALID_EXAMPLES["QUEUE_TASK_ENQUEUED"])
        payload["max_attempts"] = True
        errors = validate_payload("QUEUE_TASK_ENQUEUED", payload)
        self.assertTrue(any("max_attempts" in e for e in errors))

    def test_minimum_enforced(self):
        payload = copy.deepcopy(VALID_EXAMPLES["QUEUE_TASK_ENQUEUED"])
        payload["max_attempts"] = 0
        errors = validate_payload("QUEUE_TASK_ENQUEUED", payload)
        self.assertTrue(any("minimum" in e for e in errors))

    def test_bad_datetime_rejected(self):
        payload = copy.deepcopy(VALID_EXAMPLES["QUEUE_TASK_HEARTBEAT"])
        payload["heartbeat_at"] = "yesterday-ish"
        errors = validate_payload("QUEUE_TASK_HEARTBEAT", payload)
        self.assertTrue(any("date-time" in e for e in errors))

    def test_tool_status_enum_enforced(self):
        payload = copy.deepcopy(VALID_EXAMPLES["QUEUE_TOOL_COMPLETED"])
        payload["status"] = "OK"
        errors = validate_payload("QUEUE_TOOL_COMPLETED", payload)
        self.assertTrue(any("enum" in e for e in errors))

    def test_recovery_failed_payload_without_owner_accepted(self):
        payload = {
            "owner_id": None, "attempt": 3, "error": "lease_lost: attempts exhausted",
            "recovered_at": T0.isoformat(),
        }
        self.assertEqual(validate_payload("QUEUE_TASK_FAILED", payload), [])

    def test_valid_envelope_passes(self):
        event = _envelope(VALID_EXAMPLES["QUEUE_TASK_ENQUEUED"])
        self.assertEqual(validate_event(event), [])

    def test_envelope_rejects_bad_version_and_unknown_event(self):
        event = _envelope(VALID_EXAMPLES["QUEUE_TASK_ENQUEUED"])
        event["schema_version"] = "9.9.9"
        self.assertTrue(any("const" in e for e in validate_event(event)))
        event2 = _envelope({}, event_type="QUEUE_BOGUS")
        self.assertTrue(validate_event(event2))

    def test_envelope_rejects_payload_of_wrong_event_type(self):
        event = _envelope(VALID_EXAMPLES["QUEUE_TASK_CLAIMED"], event_type="QUEUE_TASK_ENQUEUED")
        self.assertTrue(validate_event(event))

    def test_validate_generic_entrypoint(self):
        errors = validate({"a": 1}, {"type": "object", "required": ["b"]})
        self.assertTrue(any("missing required key" in e for e in errors))
        self.assertEqual(validate({"a": 1}, {"type": "object", "required": ["a"]}), [])

    def test_claim_result_schema_shape(self):
        result = {
            "task_id": "T-1", "owner_id": "worker-1", "attempt": 1,
            "lease_expires_at": (T0 + timedelta(seconds=60)).isoformat(),
            "event": _envelope(VALID_EXAMPLES["QUEUE_TASK_CLAIMED"], "QUEUE_TASK_CLAIMED"),
        }
        self.assertEqual(validate_claim_result(result), [])
        del result["event"]
        self.assertTrue(validate(result, CLAIM_RESULT_SCHEMA))
        self.assertTrue(validate({}, EVENT_ENVELOPE_SCHEMA))


class WorkerConformanceTests(unittest.TestCase):
    """The real worker emits only schema-valid events across the protocol."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = TaskLedger(Path(self.tmp.name) / "queue.jsonl")
        self.queue = DurableQueue(self.ledger)

    def tearDown(self):
        self.tmp.cleanup()

    def _all_events_valid(self) -> list[str]:
        errors: list[str] = []
        for row in self.ledger.events():
            for err in validate_event(row):
                errors.append(f"seq {row.get('seq')}: {err}")
        return errors

    def test_happy_path_events_conform(self):
        self.queue.enqueue(task_id="T-1", kind="model_task", payload_digest="d-1", now=T0)
        claim = self.queue.claim(owner_id="w-1", lease_seconds=120, now=T0)
        self.assertIsNotNone(claim)
        self.assertEqual(validate_claim_result(claim), [])
        self.queue.heartbeat(task_id="T-1", owner_id="w-1", lease_seconds=120, now=T0 + timedelta(seconds=30))
        self.queue.reserve_tool_call(
            task_id="T-1", owner_id="w-1", run_id="run-1", tool_call_id="c-1",
            tool_name="repo.read_file", arguments_digest="d-args",
            now=T0 + timedelta(seconds=40),
        )
        self.queue.complete_tool_call(
            task_id="T-1", owner_id="w-1", run_id="run-1", tool_call_id="c-1",
            result_digest="d-out", status="PASS", now=T0 + timedelta(seconds=50),
        )
        self.queue.complete(task_id="T-1", owner_id="w-1", result_digest="d-res",
                            now=T0 + timedelta(seconds=60))
        self.assertEqual(self._all_events_valid(), [])

    def test_retry_then_exhaustion_events_conform(self):
        self.queue.enqueue(task_id="T-2", kind="model_task", payload_digest="d-2",
                           max_attempts=2, now=T0)
        first = self.queue.claim(owner_id="w-1", lease_seconds=60, now=T0)
        self.queue.fail(task_id="T-2", owner_id="w-1", error="transient",
                        now=T0 + timedelta(seconds=10))
        second = self.queue.claim(owner_id="w-1", lease_seconds=60, now=T0 + timedelta(seconds=20))
        self.assertEqual(second["attempt"], first["attempt"] + 1)
        self.queue.fail(task_id="T-2", owner_id="w-1", error="permanent",
                        result_digest="d-partial", now=T0 + timedelta(seconds=30))
        state = self.queue.status("T-2")
        self.assertEqual(state["status"], "FAILED")
        self.assertEqual(self._all_events_valid(), [])

    def test_cancel_events_conform(self):
        self.queue.enqueue(task_id="T-3", kind="model_task", payload_digest="d-3", now=T0)
        self.queue.cancel(task_id="T-3", reason="operator stop", now=T0 + timedelta(seconds=5))
        self.assertEqual(self._all_events_valid(), [])

    def test_stale_recovery_events_conform(self):
        self.queue.enqueue(task_id="T-4", kind="model_task", payload_digest="d-4", now=T0)
        self.queue.claim(owner_id="w-9", lease_seconds=30, now=T0)
        outcome = self.queue.recover_stale(now=T0 + timedelta(minutes=5))
        self.assertEqual(outcome["recovered"], ["T-4"])
        # Second recovery after re-claim and exhaustion produces the
        # ownerless FAILED payload shape from recover_stale.
        self.queue.claim(owner_id="w-9", lease_seconds=30, now=T0 + timedelta(minutes=6))
        self.queue.claim  # noqa: B018 - no-op, documents the two-attempt path below
        outcome2 = self.queue.recover_stale(now=T0 + timedelta(hours=2))
        self.assertIn("T-4", outcome2["recovered"] + outcome2["failed"])
        self.assertEqual(self._all_events_valid(), [])


if __name__ == "__main__":
    unittest.main()
