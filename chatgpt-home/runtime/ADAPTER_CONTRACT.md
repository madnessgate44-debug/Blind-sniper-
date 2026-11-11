# Runtime Adapter Contract

## Purpose
Provide a common boundary between Blind Sniper's native orchestration, task-scoped tools, GitHub control plane and native browser. External agent runtimes are not accepted execution providers.

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
| Native model provider | `scripts/blind_sniper_model_worker.py` — OpenAI-compatible HTTPS transport and bounded function-call loop | IMPLEMENTED / live provider host UNVERIFIED |
| Native tool runtime | `scripts/blind_sniper_tool_runtime.py` — three static task-scoped tools with lease-bound receipts | IMPLEMENTED / host execution UNVERIFIED |
| Native queue lifecycle | `scripts/blind_sniper_worker.py` + `scripts/blind_sniper_agent_runtime.py` | PARTIAL; private remote cross-run durability and payload recovery unverified |
| Native browser | `scripts/blind_sniper_tool_runtime.py` → `scripts/blind_sniper_browser.py` under queue lease | IMPLEMENTED / persistent host unverified |
| Native worker daemon | `scripts/blind_sniper_daemon.py` — private task-file poller, local durable ledger, health and notification outbox | PARTIAL / host activation unverified |
| GitHub Actions | Commit-triggered CI and bounded workflows | PARTIAL; ephemeral runner only |

No OpenHands, Forge or external agent/browser adapter participates in the execution path. Provider
inference is a direct host-configured HTTPS request; provider credentials are read only from host
environment variables.

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
