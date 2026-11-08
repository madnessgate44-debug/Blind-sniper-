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

## Acceptance
An adapter is not READY until a harmless task completes dispatch → receipt → execution → artifact retrieval → independent verification → state sync twice consecutively.
