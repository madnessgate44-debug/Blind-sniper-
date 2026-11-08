# Blind Sniper Execution Engine

**Entrypoint:** `scripts/blind_sniper_runtime.py`  
**Registry source:** `chatgpt-home/runtime/*.json`  
**Status:** Executable planning and guarded lifecycle state machine, with a native append-only task ledger. It is not yet a distributed runner or cross-runner task store.

## What is executable now

The engine reads the current registries and:
1. Routes a task to a registered workflow, unless the caller names one explicitly.
2. Selects the matching operating profile.
3. Resolves eligible agent roles from that profile.
4. Selects skills from the profile using deterministic task-keyword matching, or validates caller-specified skills.
5. Resolves selected skill paths and fails if a selected contract is missing.
6. Resolves every workflow adapter and normalizes its evidence status to AVAILABLE, PARTIAL, BLOCKED or UNVERIFIED.
7. Calculates readiness and the next safe action.
8. Enforces task-state transitions, explicit Owner approval, verification and independent-review gates.
9. Persists task state as JSON with an append-only transition event list.\n10. Provides a separate native JSONL task ledger with process locking, idempotency keys, sequence checks and a SHA-256 hash chain.

## Commands

Create a task JSON file from `templates/TASK_ENVELOPE.json`, ensuring that `task_id` is a stable correlation ID and `objective` is non-empty.

```bash
python scripts/blind_sniper_runtime.py plan --task-file task.json --output task-state.json
python scripts/blind_sniper_runtime.py transition --state-file task-state.json --to INSPECTING --output task-state.json
```

Advance through the documented sequence:
`REQUESTED → INSPECTING → SPECIFIED → PLANNED → EXECUTING → VERIFYING → REVIEWING → CLOSED`.

For `VERIFYING → REVIEWING`, provide an evidence JSON file containing `{"verification_passed": true}`. For `REVIEWING → CLOSED`, provide `{"review_verdict": "PASS"}`. A transition into EXECUTING is rejected if a required adapter is BLOCKED/UNVERIFIED or an Owner approval is pending. The `--owner-approved` flag records an explicit approval supplied by the authorized caller; it does not grant approval by itself.

## Routing policy

| Task intent | Workflow | Profile |
|---|---|---|
| Research / investigate / compare | `research-and-synthesis` | `research` |
| Implement / build / fix / test | `inspect-plan-implement-verify` | `engineering` |
| Review / audit | `independent-review` | `review` |
| Release / merge / deploy | `release-gate` | `release` |
| Recover / restore / reconcile | `recovery-and-reconciliation` | `recovery` |
| Other owner task | `task-control-loop` | `blind-sniper` |

Explicit `workflow`, `profile` and `skills` values are validated against the registries; unknown values fail closed.

## Important boundaries

- Planning is not dispatch. The engine never claims that an agent ran or that an adapter was invoked.
- An AVAILABLE adapter means the current host inventory declared it callable at registry refresh; the host must still recheck it at use time.
- PARTIAL means host-assisted execution only. BLOCKED or UNVERIFIED prevents transition into EXECUTING.
- Agent contracts are selected and referenced; this engine does not spawn agents.
- Skills are selected and referenced; the host must retrieve and read each selected contract before applying it.
- Hook contracts remain manual host-boundary procedures in ChatGPT; this engine does not install Claude/Codex/OpenHands hooks.
- No merge, deployment, secret mutation, permission change, paid provisioning or destructive action is performed.
- The browser workflow remains blocked until a durable supported host and authenticated connector are actually registered.

## Verification

The GitHub Actions runtime workflow runs:
```bash
python scripts/validate_blind_sniper_runtime.py
python -m unittest discover -s tests -p 'test_*.py' -v
```

Tests cover workflow/profile routing, skill and agent selection, capability readiness, unknown workflow rejection, blocked browser adapter rejection, Owner approval, lifecycle sequencing, verification, review and closure guards.


## Native task ledger (new)

**Module:** `scripts/blind_sniper_ledger.py`

The ledger stores append-only JSONL events. Each event carries a global sequence number, task ID, event type, idempotency key, timestamp, payload, previous-event hash and its own SHA-256 hash. Reads validate the full chain and fail closed on malformed or tampered records. Appends use an exclusive OS file lock, flush and fsync; repeated identical idempotency keys return the original event, while key reuse with different content is rejected.

Example:
```python
from scripts.blind_sniper_ledger import TaskLedger

ledger = TaskLedger(".blind-sniper/state/events.jsonl")
ledger.append(
    task_id="BS-20261108-001",
    event_type="TASK_CREATED",
    payload={"objective": "Example"},
    idempotency_key="BS-20261108-001:create",
)
snapshot = ledger.task_history("BS-20261108-001")
```

**Persistence boundary:** this provides process-restart recovery only when the workspace and ledger file persist. GitHub-hosted ephemeral runners do not share this local file automatically. Cross-runner durability and multi-writer compare-and-swap synchronization are not implemented yet. Do not store secrets in event payloads.


### Ledger CLI

```bash
python scripts/blind_sniper_ledger.py append \
  --ledger .blind-sniper/state/events.jsonl \
  --task-id BS-20261108-001 \
  --event-type TASK_CREATED \
  --idempotency-key BS-20261108-001:create \
  --payload-file task-event.json

python scripts/blind_sniper_ledger.py show \
  --ledger .blind-sniper/state/events.jsonl \
  --task-id BS-20261108-001
```

The `show` command validates the complete hash chain before returning task history. The CLI does not yet push events to GitHub or synchronize across runners.
