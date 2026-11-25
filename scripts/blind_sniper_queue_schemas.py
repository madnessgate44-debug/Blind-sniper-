"""Formal per-object schemas for the durable worker queue adapter.

Every event payload the queue protocol can emit (PR65 adapter surface) gets an
explicit closed schema here, plus the ledger event envelope and the claim
result object returned to callers. Schemas are data, not code conventions:
each one names its required fields, allowed types and closed key set so a
malformed payload fails loudly at the boundary instead of surfacing as a
``KeyError`` or silent ``None`` three replays later.

The validator is stdlib-only on purpose: the queue and ledger are
stdlib-only, so their contract check must not add a dependency.

Covered objects:
- Ledger event envelope (schema_version/seq/task_id/event_type/
  idempotency_key/created_at/payload/prev_hash/event_hash).
- One payload schema per queue event type (ENQUEUED, CLAIMED, HEARTBEAT,
  COMPLETED, FAILED, CANCELLED, RECOVERED, RETRY_SCHEDULED,
  QUEUE_TOOL_STARTED, QUEUE_TOOL_COMPLETED, QUEUE_TOOL_FAILED).
- The claim result object returned by ``DurableQueue.claim``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

SCHEMA_VERSION = "1.0.0"

# -- primitive helpers --------------------------------------------------------

_STRING = {"type": "string", "minLength": 1}
_STRING_OPTIONAL = {"type": ["string", "null"]}
_DATETIME = {"type": "string", "format": "date-time"}
_DIGEST = {"type": "string", "minLength": 1}
_ATTEMPT = {"type": "integer", "minimum": 0}
_POSITIVE_INT = {"type": "integer", "minimum": 1}


def _payload_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    """A closed object schema: exactly these keys, no extras."""
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(required),
        "additionalProperties": False,
    }


# -- event payload schemas ----------------------------------------------------
# One entry per event type emitted by scripts/blind_sniper_worker.py.
# Keep in sync with the worker; tests prove the worker's emissions conform.

PAYLOAD_SCHEMAS: dict[str, dict[str, Any]] = {
    "QUEUE_TASK_ENQUEUED": _payload_schema(
        {
            "kind": _STRING,
            "payload_digest": _DIGEST,
            "max_attempts": _POSITIVE_INT,
            "enqueued_at": _DATETIME,
        },
        ["kind", "payload_digest", "max_attempts", "enqueued_at"],
    ),
    "QUEUE_TASK_CLAIMED": _payload_schema(
        {
            "owner_id": _STRING,
            "attempt": _POSITIVE_INT,
            "lease_expires_at": _DATETIME,
            "heartbeat_at": _DATETIME,
        },
        ["owner_id", "attempt", "lease_expires_at", "heartbeat_at"],
    ),
    "QUEUE_TASK_HEARTBEAT": _payload_schema(
        {
            "owner_id": _STRING,
            "lease_expires_at": _DATETIME,
            "heartbeat_at": _DATETIME,
        },
        ["owner_id", "lease_expires_at", "heartbeat_at"],
    ),
    "QUEUE_TASK_COMPLETED": _payload_schema(
        {
            "owner_id": _STRING,
            "result_digest": _DIGEST,
            "completed_at": _DATETIME,
        },
        ["owner_id", "result_digest", "completed_at"],
    ),
    "QUEUE_TASK_FAILED": _payload_schema(
        {
            # Emitted by fail() (owner_id, failed_at, optional result_digest)
            # and by recover_stale() (owner_id may be null, recovered_at).
            "owner_id": _STRING_OPTIONAL,
            "attempt": _POSITIVE_INT,
            "error": _STRING,
            "failed_at": _DATETIME,
            "recovered_at": _DATETIME,
            "result_digest": _DIGEST,
        },
        ["owner_id", "attempt", "error"],
    ),
    "QUEUE_TASK_CANCELLED": _payload_schema(
        {
            "reason": _STRING,
            "cancelled_at": _DATETIME,
        },
        ["reason", "cancelled_at"],
    ),
    "QUEUE_TASK_RECOVERED": _payload_schema(
        {
            "previous_owner": _STRING_OPTIONAL,
            "attempt": _ATTEMPT,
            "reason": _STRING,
            "recovered_at": _DATETIME,
        },
        ["previous_owner", "attempt", "reason", "recovered_at"],
    ),
    "QUEUE_TASK_RETRY_SCHEDULED": _payload_schema(
        {
            "owner_id": _STRING,
            "attempt": _POSITIVE_INT,
            "error": _STRING,
            "failed_at": _DATETIME,
            "result_digest": _DIGEST,
        },
        ["owner_id", "attempt", "error", "failed_at"],
    ),
    "QUEUE_TOOL_STARTED": _payload_schema(
        {
            "owner_id": _STRING,
            "run_id": _STRING,
            "tool_call_id": _STRING,
            "tool_name": _STRING,
            "arguments_digest": _DIGEST,
            "started_at": _DATETIME,
        },
        ["owner_id", "run_id", "tool_call_id", "tool_name", "arguments_digest", "started_at"],
    ),
    "QUEUE_TOOL_COMPLETED": _payload_schema(
        {
            "owner_id": _STRING,
            "run_id": _STRING,
            "tool_call_id": _STRING,
            "status": {"type": "string", "enum": ["PASS", "FAIL"]},
            "result_digest": _DIGEST,
            "completed_at": _DATETIME,
        },
        ["owner_id", "run_id", "tool_call_id", "status", "result_digest", "completed_at"],
    ),
    "QUEUE_TOOL_FAILED": _payload_schema(
        {
            "owner_id": _STRING,
            "run_id": _STRING,
            "tool_call_id": _STRING,
            "status": {"type": "string", "enum": ["PASS", "FAIL"]},
            "result_digest": _DIGEST,
            "completed_at": _DATETIME,
        },
        ["owner_id", "run_id", "tool_call_id", "status", "result_digest", "completed_at"],
    ),
}

EVENT_TYPES = tuple(sorted(PAYLOAD_SCHEMAS))

# -- envelope and result-object schemas ---------------------------------------

EVENT_ENVELOPE_SCHEMA: dict[str, Any] = _payload_schema(
    {
        "schema_version": {"type": "string", "const": SCHEMA_VERSION},
        "seq": _POSITIVE_INT,
        "task_id": _STRING,
        "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
        "idempotency_key": _STRING,
        "created_at": _DATETIME,
        "payload": {"type": "object"},
        "prev_hash": _STRING,
        "event_hash": _STRING,
    },
    [
        "schema_version", "seq", "task_id", "event_type", "idempotency_key",
        "created_at", "payload", "prev_hash", "event_hash",
    ],
)

CLAIM_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task_id": _STRING,
        "owner_id": _STRING,
        "attempt": _POSITIVE_INT,
        "lease_expires_at": _DATETIME,
        "event": EVENT_ENVELOPE_SCHEMA,
    },
    "required": ["task_id", "owner_id", "attempt", "lease_expires_at", "event"],
    "additionalProperties": False,
}


# -- stdlib-only validator ----------------------------------------------------

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _is_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Validate ``instance`` against ``schema``; return a list of error strings.

    Supports the subset this contract uses: type (single or union), properties,
    required, additionalProperties: False, enum, const, minLength, minimum and
    format: date-time. Empty list means valid.
    """
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        allowed = expected if isinstance(expected, list) else [expected]
        if not any(_TYPE_CHECKS[t](instance) for t in allowed):
            errors.append(f"{path}: expected type {'/'.join(allowed)}, got {type(instance).__name__}")
            return errors
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']!r}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if schema.get("format") == "date-time" and not _is_datetime(instance):
            errors.append(f"{path}: not an ISO date-time: {instance!r}")
    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required key {key!r}")
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{path}: unexpected key {key!r}")
        for key, subschema in props.items():
            if key in instance:
                errors.extend(validate(instance[key], subschema, f"{path}.{key}"))
    return errors


def validate_payload(event_type: str, payload: dict[str, Any]) -> list[str]:
    """Validate one event payload against its event type's schema."""
    schema = PAYLOAD_SCHEMAS.get(event_type)
    if schema is None:
        return [f"$.event_type: unknown queue event type {event_type!r}"]
    return validate(payload, schema, f"$.payload({event_type})")


def validate_event(event: dict[str, Any]) -> list[str]:
    """Validate a full ledger event: envelope, then payload by event type."""
    errors = validate(event, EVENT_ENVELOPE_SCHEMA, "$")
    if errors:
        return errors
    return validate_payload(event["event_type"], event["payload"])


def validate_claim_result(result: dict[str, Any]) -> list[str]:
    """Validate the object DurableQueue.claim returns to its caller."""
    errors = validate(result, CLAIM_RESULT_SCHEMA, "$")
    if errors:
        return errors
    return validate_event(result["event"])
