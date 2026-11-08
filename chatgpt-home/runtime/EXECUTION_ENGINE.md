# Blind Sniper Execution Engine

**Entrypoint:** `scripts/blind_sniper_runtime.py`  
**Ledger:** `scripts/blind_sniper_ledger.py`  
**Status:** Native planner, guarded lifecycle, automatic local ledger persistence and replay. Not a distributed runner.

## Runtime contract

The engine:
1. Routes a task through the checked-in workflow registry.
2. Selects its profile from host policy; task JSON cannot choose its own profile.
3. Resolves native agent contracts and skill paths.
4. Checks required adapter capability status and computes readiness.
5. Creates a task-state snapshot and commits it to the native ledger.
6. Persists every accepted lifecycle transition to the ledger before updating the convenience state file.
7. Reconstructs the latest committed state from the verified ledger after interruption.
8. Enforces approval, host-forbidden-action, verification and independent-review gates.

Planning and state persistence do not mean an agent was spawned or work was executed. Native agent contracts remain role specifications; the engine does not currently run separate model processes.

## Commands

Use a stable task ID and a non-empty objective in the task JSON.

```bash
python scripts/blind_sniper_runtime.py plan \
  --task-file task.json --output task-state.json \
  --ledger .blind-sniper/state/events.jsonl

python scripts/blind_sniper_runtime.py transition \
  --state-file task-state.json --to INSPECTING \
  --output task-state.json --ledger .blind-sniper/state/events.jsonl

python scripts/blind_sniper_runtime.py recover \
  --task-id BS-20261108-001 \
  --output recovered-state.json \
  --ledger .blind-sniper/state/events.jsonl
```

The ledger defaults to `.blind-sniper/state/events.jsonl` if `--ledger` is omitted. Keep this file in a persistent workspace; ephemeral CI runners do not share it.

## Lifecycle and policy

`REQUESTED → INSPECTING → SPECIFIED → PLANNED → EXECUTING → VERIFYING → REVIEWING → CLOSED`

- Every accepted transition appends a full state snapshot to the hash-chained ledger.
- The ledger append happens before the JSON checkpoint write. If the process stops between those operations, the next transition reloads the ledger's latest state. Repeating the already-committed target is idempotent and only repairs the checkpoint.
- Legacy task JSON without ledger history is adopted once as `TASK_IMPORTED`; subsequent transitions use ledger state as authoritative.
- Unknown/unclassified requested actions require explicit action-specific Owner approval.
- Host-forbidden actions (including force-push, branch deletion, credential/secret export, disabling branch protection and unbounded shell execution) cannot be overridden by task JSON or an approval record.
- Other consequential actions, including merges, default-branch pushes, deployments, CI/CD edits, secret/permission changes, paid provisioning and destructive production-data changes, remain approval-gated.
- The task envelope cannot select its own profile or forbidden-action policy.
- The transition CLI accepts host-supplied approval records with action, approver, verbatim words and an offset-aware timestamp. These are auditable assertions, not cryptographic proof of the identity of the person who supplied the file.
- `VERIFYING → REVIEWING` requires `verification_passed=true`.
- `REVIEWING → CLOSED` requires PASS, a reviewer distinct from the implementer, matching task ID, full commit SHA and CI run ID. Metadata checks do not cryptographically authenticate the reviewer.

## Recovery and persistence boundary

`TaskLedger` validates the global sequence and SHA-256 hash chain before returning history. It uses process locking, fsync and idempotency keys. Runtime snapshots are stored as `TASK_CREATED`, `TASK_IMPORTED` and `TASK_TRANSITIONED` events. The `recover` command restores the latest snapshot for a task.

This is local-workspace persistence only. It does not yet provide cross-runner durability, GitHub-backed compare-and-swap, multi-host leases or distributed concurrency control. The hash chain detects accidental or unsophisticated edits; it is not a signed tamper-proof audit log.

## Capability boundaries

- BLOCKED or UNVERIFIED required adapters prevent entry into EXECUTING.
- PARTIAL means host-assisted execution only.
- An AVAILABLE adapter must still be rechecked by the host immediately before invocation.
- Agent contracts are selected and referenced; this engine does not spawn agents.
- Skills are selected and referenced; the host must read the selected contract before applying it.
- Browser, persistent background execution and generic shell execution remain unavailable unless a real host adapter is registered and verified.
- No merge, deployment, secret mutation, permission change, paid provisioning or destructive action is performed by this runtime.

## Verification

Runtime CI runs:

```bash
python scripts/validate_blind_sniper_runtime.py
python -m unittest discover -s tests -p 'test_*.py' -v
```

Tests cover registry resolution, routing, task-envelope authority boundaries, Owner approval records, host-forbidden actions, correlated review receipts, ledger persistence, stale-checkpoint recovery and replay.
