# Runtime Adapter Contract

## Purpose
Provide a common boundary between Blind Sniper orchestration and execution providers (GitHub Actions, OpenHands, Forge, Codex CLI or future runners).

## Required operations
- `capabilities()`: report supported operations, auth state, limits and cost class.
- `dispatch(task_envelope)`: submit a uniquely identified task.
- `status(run_id)`: retrieve current state.
- `artifacts(run_id)`: retrieve logs, diff, tests and outputs.
- `cancel(run_id)`: stop a running task where supported.
- `callback(receipt)`: persist final state to the canonical task hub.

## Required guarantees
- Stable task/correlation ID.
- Idempotent dispatch or duplicate detection.
- Explicit permission scope and workspace.
- Isolated branch/worktree for concurrent writes.
- Timeout and bounded retry.
- Secret redaction.
- Artifact provenance tied to exact commit/tree.
- No success state without retrieved evidence.

## Provider mapping
| Provider | Dispatch | Status | Artifacts | Current state |
|---|---|---|---|---|
| GitHub Actions | Commit-triggered workflow; no generic dispatch action currently exposed | Workflow run APIs | Logs/artifacts | PARTIAL |
| OpenHands Cloud V1 | `scripts/blind_sniper_openhands_cloud.py` (create conversation, poll start task, status/messages/artifacts, cancel) | Bearer `OPENHANDS_CLOUD_API_KEY`; mock-tested | Trajectory download / events | IMPLEMENTED, DISABLED WITHOUT SECRET |
| Forge MCP | `scripts/blind_sniper_forge_mcp.py` (Streamable HTTP; initialize / tools/list / tools/call) | Bearer `FORGE_MCP_TOKEN`; mock-tested | Audit receipts | IMPLEMENTED, DISABLED WITHOUT TOKEN; direct ChatGPT connector BLOCKED |
| Model worker | `scripts/blind_sniper_model_worker.py` (independent agent invocations) | `BLIND_SNIPER_MODEL_API_KEY`; mock-tested | Redacted receipts | IMPLEMENTED, DISABLED WITHOUT KEY |
| Durable queue | `scripts/blind_sniper_queue.py`, `scripts/blind_sniper_worker.py` | Logical persistence over the ledger | Health/digest receipts | IMPLEMENTED, TRIGGER NOT ACTIVATED |
| Codex CLI | Host invocation | Host runtime required | Local filesystem/worktree | NOT AVAILABLE HERE |

## Continuous-autonomy adapters

Four adapters implement R1–R5. Each is disabled without its secret and is
contract-tested against an injected fake transport, so no live call is made in
CI and no cost is assumed.

- **Model worker (R1).** `ModelAgent` carries a distinct `agent_id`, its own
  system prompt and an enforced tool allowlist. `ModelInvoker.invoke` makes a
  real separate call with fresh context, bounded timeout, bounded retries and a
  redacted receipt; `invoke_many` runs a bounded concurrency pool. A requested
  tool outside the allowlist is refused.
- **Durable queue (R2).** `DurableQueue` implements enqueue / claim / lease /
  heartbeat / cancel / recovery / reconciliation over the append-only ledger.
  Contention is first-writer-wins by event sequence. `recover_stale` reclaims
  expired leases idempotently. Only a `payload_ref` and `payload_hash` are
  stored; private payload bodies never enter the ledger. This is *logical*
  durability (replayed on each invocation), never a resident process.
- **OpenHands Cloud V1 (R3).** `OpenHandsCloudClient` implements the documented
  V1 endpoints with bearer auth, redaction and idempotent dispatch. It refuses
  to act when the secret is absent.
- **Forge MCP (R4).** `ForgeMCPClient` speaks Streamable HTTP JSON-RPC
  (initialize / tools/list / tools/call), enforces a tool allowlist, requires an
  explicit approval reference for browser write tools, and records redacted
  audit receipts. It does not claim a direct ChatGPT connector.

## Native browser adapter

The browser mechanics live in `scripts/blind_sniper_browser.py`; the native lease-gated dispatch boundary lives in `scripts/blind_sniper_browser_dispatch.py`.

The dispatch boundary requires:
- An authoritative ledger snapshot with task status `EXECUTING`.
- Host owner identity equal to the task's `implementer_id`.
- A currently active lease owned by that identity, with timeout plus safety margin remaining.
- A unique run/session/step reservation before browser invocation.
- A completion event carrying the adapter receipt after the action.

A started event without a completion event is a reconciliation state, not permission to replay. The bridge uses the existing local or GitHub Contents CAS ledger selected by runtime arguments. Browser policy remains host-supplied; task envelopes cannot grant their own lease or write approval.

## Remaining adapter gaps

- GitHub Actions remains an ephemeral runner, not a persistent browser service.
- No direct ChatGPT browser tool/connector registration is established.
- Tabs/frames, approved workspace upload, bounded download and PDF export are implemented and passed two-cycle real Chromium E2E (run 42496827462). Authenticated profiles/cookies remain intentionally unsupported. Persistent host and cross-job browser recovery are pending actual Oracle VM provisioning and the opt-in two-job acceptance workflow.
- The browser allowlist is not an OS firewall; host/container egress restrictions remain a separate defense-in-depth control.
