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
| OpenHands | GitHub App mention route | Session API not exposed in this session | Task-specific output pending | PARTIAL |
| Forge | HTTP MCP design in Firstborn PR #147 | Connector not registered here | Not retrieved through MCP here | BLOCKED |
| Codex CLI | Host invocation | Host runtime required | Local filesystem/worktree | NOT AVAILABLE HERE |

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
- Tabs/frames, uploads/downloads, PDF, authenticated profiles, cookies and live browser recovery are not implemented.
- The browser allowlist is not an OS firewall; host/container egress restrictions remain a separate defense-in-depth control.
