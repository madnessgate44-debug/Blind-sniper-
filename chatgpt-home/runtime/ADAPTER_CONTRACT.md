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

| Provider / subsystem | Boundary | Current state |
|---|---|---|
| Native model provider | `scripts/blind_sniper_model_worker.py` — OpenAI-compatible HTTPS transport configured by host environment | IMPLEMENTED / live round trip UNVERIFIED |
| Native queue lifecycle | `scripts/blind_sniper_worker.py` + `scripts/blind_sniper_agent_runtime.py` | IMPLEMENTED locally; private remote durability requires host configuration |
| GitHub Actions | Commit-triggered CI and bounded workflows | PARTIAL; ephemeral runner only |
| Native browser | `scripts/blind_sniper_browser.py` + lease-gated dispatcher | PARTIAL; persistent host unverified |

No OpenHands, Forge or other external agent/browser client is part of the Blind Sniper execution
architecture. Their former adapter modules and tests have been removed. Model inference is a
provider request made directly by Blind Sniper; provider choice, credentials and quota remain host
configuration. No provider credential is stored in this repository.

### Native model provider and queue lifecycle

`NativeModelInvoker` creates a new request with a fresh system/user context for every task. It
requires a configured model name and HTTPS-compatible base URL, supports an optional environment-
supplied API key, enforces a context-size bound and transport timeout, redacts output and returns a
unique run ID plus output digest. It refuses provider tool calls and non-empty tool allowlists until
the native executor is available.

`scripts/blind_sniper_agent_runtime.py` connects the model worker to the durable queue:
digest-bound enqueue/validation → exclusive claim → lease heartbeat → model invocation → result
digest completion or bounded retry. The queue stores no private payload. The host must keep task
input and result artifacts outside this public repository and re-supply the same payload on retry.
The private GitHub Contents CAS adapter remains host-configured and must target a private repo.

The provider transport and queue lifecycle are contract-tested with a deterministic fake HTTP
transport and the real local ledger. These tests prove request shape and lifecycle wiring, not a
live model response or remote cross-run persistence. No provider credentials are present in CI.

### Native autonomy gate

The autonomy runner is a bounded single pass, not a daemon. Its activation gate now requires a
native provider configuration and deliberately reports the executor prerequisite as false until
the task-scoped native executor/tool registry exists. No scheduled trigger is activated.

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
