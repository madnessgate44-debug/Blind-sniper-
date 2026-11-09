# Blind Sniper Execution Engine

**Entrypoint:** `scripts/blind_sniper_runtime.py`  
**Ledger implementation:** `scripts/blind_sniper_ledger.py`  
**Status:** Native planner, guarded lifecycle, automatic local persistence/replay and optional GitHub Contents API persistence. Not a distributed agent executor.

## Runtime contract

The engine:
1. Routes a task through the checked-in workflow registry.
2. Selects its profile from host policy; task JSON cannot choose its own profile.
3. Resolves native agent contracts and skill paths.
4. Checks required adapter capability status and computes readiness.
5. Persists a task-created snapshot to the selected ledger.
6. Persists every accepted lifecycle transition before updating the convenience JSON checkpoint.
7. Reconstructs the latest committed state from the verified ledger after interruption.
8. Enforces approval, host-forbidden-action, verification and independent-review gates.

Planning and state persistence do not mean an agent was spawned or work was executed. Native agent contracts remain role specifications; the engine does not currently run separate model processes.

## Commands — local ledger (default)

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

python scripts/blind_sniper_runtime.py claim \
  --task-id BS-20261108-001 --owner-id runner-01 \
  --lease-seconds 300 --idempotency-key BS-20261108-001:claim-01 \
  --ledger .blind-sniper/state/events.jsonl

python scripts/blind_sniper_runtime.py transition \
  --state-file task-state.json --to EXECUTING --lease-owner runner-01 \
  --output task-state.json --ledger .blind-sniper/state/events.jsonl

python scripts/blind_sniper_runtime.py release \
  --task-id BS-20261108-001 --owner-id runner-01 \
  --idempotency-key BS-20261108-001:release-01 \
  --ledger .blind-sniper/state/events.jsonl
```

## Commands — optional GitHub-backed ledger

Supply a token through an environment variable; never place it in task JSON, command-line arguments, logs or repository files.

```bash
export GITHUB_TOKEN="<host-provided token with Contents write access>"

python scripts/blind_sniper_runtime.py plan \
  --task-file task.json --output task-state.json \
  --github-ledger --github-owner OWNER --github-repo REPOSITORY \
  --github-branch integration --github-path .blind-sniper/state/events.jsonl

python scripts/blind_sniper_runtime.py transition \
  --state-file task-state.json --to INSPECTING --output task-state.json \
  --github-ledger --github-owner OWNER --github-repo REPOSITORY \
  --github-branch integration

python scripts/blind_sniper_runtime.py recover \
  --task-id BS-20261108-001 --output recovered-state.json \
  --github-ledger --github-owner OWNER --github-repo REPOSITORY \
  --github-branch integration

python scripts/blind_sniper_runtime.py claim \
  --task-id BS-20261108-001 --owner-id runner-01 \
  --lease-seconds 300 --idempotency-key BS-20261108-001:claim-01 \
  --github-ledger --github-owner OWNER --github-repo REPOSITORY \
  --github-branch integration

python scripts/blind_sniper_runtime.py transition \
  --state-file task-state.json --to EXECUTING --lease-owner runner-01 \
  --output task-state.json --github-ledger --github-owner OWNER \
  --github-repo REPOSITORY --github-branch integration

python scripts/blind_sniper_runtime.py release \
  --task-id BS-20261108-001 --owner-id runner-01 \
  --idempotency-key BS-20261108-001:release-01 \
  --github-ledger --github-owner OWNER --github-repo REPOSITORY \
  --github-branch integration
```

The GitHub adapter first checks repository metadata and refuses any target where GitHub does not report `private: true`. It then reads the current file SHA, validates the complete event chain, applies the append or lease mutation locally, and writes the new JSONL content using the prior SHA as a compare-and-swap precondition. HTTP 409/422 conflicts trigger bounded reload-and-retry (three attempts by default). Competing claims are re-evaluated against the latest ledger before one can win. Repeated idempotency keys do not create extra commits. Each successful append creates a Git commit; this is intended for small control-plane event files, not transcripts or large artifacts.

**Operational limitation:** GitHub-backed adapter behavior is unit-tested with a mocked Contents API. No live write was performed. The checked-in Actions workflow currently declares `contents: read`, so its token cannot use this write adapter. Enabling write access in workflows was not part of this change and remains an explicit future permission decision. A host must provide a token with Contents write permission and an authorized target branch.

## Lifecycle and policy

`REQUESTED → INSPECTING → SPECIFIED → PLANNED → EXECUTING → VERIFYING → REVIEWING → CLOSED`

- Every accepted transition appends a full state snapshot to the ledger.
- The ledger append happens before the JSON checkpoint write. If the process stops between those operations, the next transition reloads the ledger's latest state. Repeating the already-committed target repairs the checkpoint without a duplicate event.
- The CLI exposes `claim`, `release` and `lease-status`. Lease duration is bounded to 1–3600 seconds. The same owner may renew with a new idempotency key; another owner is blocked until expiry or release. Tasks with a latest state of CLOSED or CANCELLED cannot be claimed.
- CLI entry into EXECUTING requires an active lease and matching `--lease-owner`. The lease check and EXECUTING event append occur under one local file lock or one GitHub blob-SHA CAS operation, avoiding a check-then-write race. The committed snapshot records that lease owner as `implementer_id`, so closure review cannot compare against a generic controller identity.
- The atomic ledger method rejects any receipt whose snapshot is not `EXECUTING` or whose embedded task ID differs from the event task ID.
- Legacy task JSON without ledger history can be adopted once as `TASK_IMPORTED`; subsequent transitions use ledger state as authoritative.
- Unknown/unclassified requested actions remain high-risk and must be checked against the active Owner delegation and host policy.
- Host-forbidden actions (force-push, branch deletion, credential/secret export, disabling branch protection and unbounded shell execution) cannot be overridden by task JSON or approval records.
- The chat interface has a standing Owner delegation for repository-scoped merge, default-branch push, CI/CD, release and eligible deployment actions in `madnessgate44-debug/Blind-sniper-`; this does not authorize those actions elsewhere.
- Runtime implementation gap: this planner currently initializes `approved_actions` as empty and requires task-correlated host approval records for consequential transitions. It does not yet load or evaluate `AUTHORITY_DELEGATION.md`; the host must not claim the runtime's automated approval gate has been upgraded merely because the conversational interface has standing authority.
- The task envelope cannot select its own profile or forbidden-action policy.
- Approval records are host-supplied assertions containing action, approver, verbatim words and an offset-aware timestamp. They are auditable metadata, not cryptographic proof of the approver's identity.
- `VERIFYING → REVIEWING` requires `verification_passed=true`.
- `REVIEWING → CLOSED` requires PASS, a reviewer distinct from the implementer, matching task ID, full commit SHA and CI run ID. Metadata checks do not cryptographically authenticate the reviewer.

## Persistence and integrity boundaries

The local `TaskLedger` uses process locking, fsync, idempotency keys, monotonic sequence validation and a SHA-256 hash chain. The optional GitHub adapter adds blob-SHA compare-and-swap and immutable Git commit history for each accepted append.

The hash chain detects edits but is not a signed tamper-proof audit log. GitHub Contents API file-level CAS is not a full worker scheduler and does not implement cancellation or stale-worker recovery scheduling. It does provide atomic ledger-backed claim/renew/release and execution-transition commits. The adapter deliberately cannot target this public repository; a private repository is required. Concurrent writes are retried a bounded number of times; sustained contention fails closed.

## Capability boundaries

- BLOCKED or UNVERIFIED required adapters prevent entry into EXECUTING.
- PARTIAL means host-assisted execution only.
- An AVAILABLE adapter must still be rechecked by the host immediately before invocation.
- Agent contracts are selected and referenced; this engine does not spawn agents.
- Skills are selected and referenced; the host must read the selected contract before applying it.
- Browser, persistent background execution and generic shell execution remain unavailable unless a real host adapter is registered and verified.
- This runtime does not itself perform merge, deployment, secret mutation, permission change, paid provisioning or destructive actions. The conversational host may perform delegated repository actions through its own authorized tools; do not conflate the two execution paths.

## Verification

Runtime CI runs:

```bash
python scripts/validate_blind_sniper_runtime.py
python -m unittest discover -s tests -p 'test_*.py' -v
```

Tests cover registry resolution, routing, task-envelope authority boundaries, Owner approval records, host-forbidden actions, correlated review receipts, local ledger persistence, GitHub CAS retries, remote hash-chain validation and recovery reads.
