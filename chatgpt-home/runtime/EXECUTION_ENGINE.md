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

- The first accepted state event stores a compact snapshot without its event history. Later transitions store a hash-verified top-level diff plus one lifecycle event; recovery rebuilds the event list from the ledger. Legacy full snapshots remain readable.
- Appends are refused when the resulting JSONL ledger would exceed 512 KiB. Keep transcripts and artifacts outside this control-plane ledger.
- The ledger append happens before the JSON checkpoint write. If the process stops between those operations, the next transition reloads the ledger's latest state. Repeating the already-committed target repairs the checkpoint without a duplicate event.
- The CLI exposes `claim`, `release` and `lease-status`. Lease duration is bounded to 1–3600 seconds. The same owner may renew with a new idempotency key; another owner is blocked until expiry or release. Tasks with a latest state of CLOSED or CANCELLED cannot be claimed.
- Entry into EXECUTING, every transition from EXECUTING/VERIFYING/REVIEWING, and same-state retries in those states require the active lease and matching `--lease-owner`. The lease check and event append occur under one local file lock or one GitHub blob-SHA CAS operation. The committed state binds `implementer_id` to that lease owner.
- GitHub-backed lease expiry uses the server's HTTP `Date` response header. If the header is absent or invalid, lease operations fail closed rather than trusting a runner's local clock.
- The atomic ledger method rejects any receipt whose snapshot is not `EXECUTING` or whose embedded task ID differs from the event task ID.
- Legacy task JSON without ledger history can be adopted only when its status is `REQUESTED`, its complete plan re-derives identically from its objective, and the host supplies one valid Owner approval for `task_import`. Approval records bind `approval_id`, `task_id`, action, approver, verbatim words, issuance time and expiry; the ledger records consumed IDs and rejects replay.
- Unknown/unclassified requested actions remain high-risk and must be checked against the active Owner delegation and host policy.
- Host-forbidden actions (force-push, branch deletion, credential/secret export, disabling branch protection and unbounded shell execution) cannot be overridden by task JSON or approval records.
- The chat interface has a standing Owner delegation for repository-scoped merge, default-branch push, CI/CD, release and eligible deployment actions in `madnessgate44-debug/Blind-sniper-`; this does not authorize those actions elsewhere.
- The planner loads the machine-readable standing delegation from `chatgpt-home/runtime/authority.json`. Only exact repository matches and explicitly allowlisted actions are auto-satisfied; task-supplied approval/delegation fields are ignored. Unknown, excluded and out-of-scope actions remain pending or host-forbidden.
- The machine-readable file is a policy mirror of `chatgpt-home/AUTHORITY_DELEGATION.md`. Keep both synchronized; malformed, missing or conflicting policy must fail closed.
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

## Native model invocation and durable task dispatch

Blind Sniper owns the model invocation boundary in `scripts/blind_sniper_model_worker.py`.
`NativeModelInvoker` sends one fresh, bounded OpenAI-compatible chat-completions request per
agent task. It does not create an external agent session, share conversation history, or delegate
orchestration. The host configures the provider; no vendor or paid service is hard-coded.

Required host environment:
- `BLIND_SNIPER_MODEL_BASE_URL` — HTTPS OpenAI-compatible API base (loopback HTTP is allowed for local testing).
- `BLIND_SNIPER_MODEL_NAME` — model identifier.
- `BLIND_SNIPER_MODEL_API_KEY` — optional provider credential, read only from the environment.
- `BLIND_SNIPER_MODEL_API_KEY_HEADER` — optional auth header override; defaults to Authorization.

No credentials belong in task files, command arguments, logs, artifacts or this public repository.
A live provider call is NOT VERIFIED until a host with an approved no-card/no-paid provider
configuration runs the real boundary and retains a redacted correlated receipt.

`scripts/blind_sniper_agent_runtime.py` connects a single model invocation to
`DurableQueue`: validate/enqueue a digest-bound task, claim a lease, heartbeat, invoke the model,
then commit a result digest or schedule a bounded retry. The queue stores only the payload digest;
the task JSON and output receipt must remain in a private host path and be supplied again on retry.
The CLI rejects task and receipt paths inside this public repository.

Example (run only on a configured private host):

```bash
python scripts/blind_sniper_agent_runtime.py \
  --task-file /private/blind-sniper/tasks/task.json \
  --output /private/blind-sniper/receipts/task-run.json \
  --github-ledger --github-owner OWNER --github-repo PRIVATE_REPO \
  --github-branch main --github-path blind-sniper-continuity/QUEUE.jsonl
```

Current boundaries:
- **R1 — IMPLEMENTED / LIVE-UNVERIFIED:** native provider transport, isolated context, identity, timeout, retry, concurrency and redacted receipt contracts; no real provider credentials or round trip verified here.
- **R2 — PARTIAL:** model dispatch is connected to queue claim/heartbeat/completion/retry; remote cross-run operation still requires the private GitHub CAS store and host-supplied private payload recovery.
- **R3 — IMPLEMENTED / HOST-UNVERIFIED:** bounded native model tool-call loop and static task-scoped tool registry exist; live provider-host execution is not verified.
- **R4 — IMPLEMENTED / PERSISTENT-HOST-UNVERIFIED:** native model tools are connected to the checked-in Chromium adapter under the active queue lease; persistent browser host and cross-job session recovery are not verified.
- **R5 — PARTIAL / HOST-ACTIVATION-UNVERIFIED:** a persistent native private-task poller, stale-lease recovery, health file and metadata-only notification outbox are implemented; no approved host service has been started.

No OpenHands, Forge, external agent runtime or external browser adapter is part of the execution path.
A scheduled Actions run is an ephemeral invocation, not a resident worker.

## Native task-scoped tool runtime

`scripts/blind_sniper_tool_runtime.py` is the only model-tool execution boundary. It exposes three
static function tools; the model cannot supply shell commands, import modules, call arbitrary URLs,
or name unregistered tools.

| Tool | Permission and scope | Execution contract |
|---|---|---|
| `repo.read_file` | Explicit task `allowed_paths`; relative workspace paths only | UTF-8 text, symlink/traversal rejection, 256 KB file cap, redacted/truncated output |
| `repo.write_file` | `workspace_write` plus an exact file path in `allowed_paths` | Atomic workspace replacement; policy/authority files and `.github/workflows/` are denied |
| `verification.run` | Fixed command ID only | `runtime-validator` or `unit-tests`; no shell and no model-supplied command arguments |

The provider receives only the current agent's registered tool schemas. The model loop is bounded to
four tool rounds and eight tool calls per invocation. Task paths and tool permissions are included
in the queue payload digest. The internal lease owner and lease duration are carried to the tool
runtime but are not exposed in model context.

Before a tool side effect, the queue appends a `QUEUE_TOOL_STARTED` event guarded by the active,
unexpired task lease. After execution it appends a terminal `QUEUE_TOOL_COMPLETED` or
`QUEUE_TOOL_FAILED` event with a result digest. Replayed call IDs and expired leases fail closed.
Tool output returned to the model is bounded; receipts contain identifiers, status and digests,
not raw task payloads.

## Native browser tools

The native tool registry exposes browser operations through the checked-in `BrowserAdapter`, not an
external browser agent:

- Read/navigation: `browser.navigate`, `browser.snapshot`, `browser.get_url`, `browser.tabs`,
  `browser.screenshot`.
- Mutating: `browser.click`, `browser.fill`, `browser.press` are offered only when the task
  carries `workspace_write`, a host approval reference is present, and the host explicitly sets
  `BLIND_SNIPER_BROWSER_WRITE_APPROVED=1`.
- Every browser action is inside the same active queue lease and tool-call reservation. The
  BrowserAdapter adds a task/run/session/step-correlated browser receipt.
- The host must configure `BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS`. Browser session state, receipts
  and screenshots are written outside the public repository workspace.
- Output is redacted and bounded before it returns to the model. No credentials/cookies are copied
  into model context by this tool contract.

The browser adapter's Chromium local-fixture acceptance is CI-tested. A persistent browser host,
authenticated session persistence, and cross-job recovery remain unverified. Browser writes remain
blocked unless host approval is explicit.

This is contract-tested against deterministic provider responses and a local ledger. A real
configured model host, private remote CAS tool receipts, and recovery of a tool call interrupted
between its start and terminal event remain host-level acceptance work. An interrupted start is
never silently replayed.

## Persistent native worker daemon

`scripts/blind_sniper_daemon.py` is the native long-running worker. It is a host process, not a
GitHub Actions schedule or an external agent. It:

1. Reads task JSON only from an owner-only private `<state-dir>/tasks/` directory outside the
   public repository.
2. Recovers expired queue leases before scanning.
3. Enqueues/claims the exact task ID and invokes the existing native model/tool runtime.
4. Writes complete task receipts to an owner-only private `receipts/` directory.
5. Writes a metadata-only `notifications.jsonl` outbox and a private `health.json` checkpoint.
6. Handles SIGTERM/SIGINT by stopping after the current bounded task.

The local append-only ledger is stored under the same private state directory and survives process
restarts on that host. Private remote CAS/cross-host recovery remains a separate unverified gate.
The notification outbox is not a delivery service; a host-side consumer is still required.

### Host setup

The service template is `deploy/blind-sniper-worker.service.example`. It expects the repository
checkout at `/opt/blind-sniper`, a service account named `blind-sniper`, and an owner-only state
directory at `/var/lib/blind-sniper`. The host administrator must provision those directories and
an environment file at `/etc/blind-sniper/worker.env`; no credentials or service account are
created by this repository.

Required host environment:
- `BLIND_SNIPER_MODEL_BASE_URL`
- `BLIND_SNIPER_MODEL_NAME`
- `BLIND_SNIPER_MODEL_API_KEY` (optional; environment only)
- `BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS` (only if browser tools are allowlisted)
- `BLIND_SNIPER_BROWSER_WRITE_APPROVED=1` only when the task carries an explicit approval
  reference and mutating browser actions are intentionally enabled.

Private task files must be named `<task_id>.json`, mode `0600`, and contain only the task envelope
fields accepted by `blind_sniper_agent_runtime.py`. The daemon refuses task files, receipts, ledger
or browser state inside the public repository workspace.

Manual one-cycle validation:

```bash
python scripts/blind_sniper_daemon.py \
  --state-dir /var/lib/blind-sniper \
  --owner-id native-worker \
  --once
```

Continuous mode is started by the host service manager using the supplied unit template. This
branch does not install, enable or start that service. Until an approved host runs it with a real
provider configuration, R1/R5 remain host-unverified; no unattended autonomy is claimed.

## Verification

Runtime CI runs:

```bash
python scripts/validate_blind_sniper_runtime.py
python -m unittest discover -s tests -p 'test_*.py' -v
```

Tests cover registry resolution, routing, task-envelope authority boundaries, Owner approval records, host-forbidden actions, correlated review receipts, local ledger persistence, GitHub CAS retries, remote hash-chain validation and recovery reads.


## Allowlisted task executor

**Entrypoint:** `scripts/blind_sniper_executor.py`  
**Workflow:** `.github/workflows/blind-sniper-allowlisted-executor.yml`  
**Task contract:** `.blind-sniper/tasks/<task>.json`  
**Runtime workflow:** `bounded-verification`

The executor accepts only the fixed command IDs `unit-tests` and `runtime-validator`. The task envelope must select the registered `bounded-verification` workflow; it cannot supply shell text or arguments. Each requested command maps to one named workflow step. The executor records RUNNING and terminal step receipts with start/completion times from GitHub's HTTP Date header, exact exit code (or timeout status), run ID, commit SHA and log line references. Commands not requested are marked NOT_REQUESTED; commands skipped after a failure are marked BLOCKED. The independent-review step remains AWAITING_INDEPENDENT_REVIEW and is never self-completed by this runner.

**Persistence is deliberately per-run and ephemeral.** The local ledger, lease and receipts are created inside one GitHub Actions run and uploaded as a 14-day artifact. They do not provide cross-run exclusion, cross-run deduplication, durable task recovery or a persistent worker. A repeated task ID in a later run is not protected by the prior run's local ledger. The workflow uses `contents: read` with `persist-credentials: false` and a full read-only checkout (no sparse-checkout), so every allowlisted command can read all of the paths its tests require, and it does not write private continuity data to this public repository.

A successful verification run ends in `REVIEWING`, not `CLOSED`. A distinct reviewer must inspect the exact commit and artifact and supply a task-correlated PASS receipt before closure. A green executor job is not an independent review or closure receipt.
