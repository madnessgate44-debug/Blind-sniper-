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


## Native browser adapter

The browser adapter is a bounded execution provider implemented in `scripts/blind_sniper_browser.py` and backed by the pinned `agent-browser@0.41.2` CLI.

Initial supported actions: `open`, `snapshot`, `click`, `fill`, `press`, `screenshot`, `get-url`, and `close`.

Host policy is supplied outside task content:
- `BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS`: comma-separated exact domains or parent domains.
- `BLIND_SNIPER_BROWSER_BLOCKED_DOMAINS`: denylist; deny takes precedence.
- `BLIND_SNIPER_BROWSER_WRITE_APPROVED=1` plus a host-supplied approval reference: required for click/fill/press.
- Only HTTP(S) URLs are accepted. Redirect destinations are checked after navigation and after mutating actions; an out-of-policy destination closes the session and produces a failed receipt.
- Browser sessions are correlated to one task/run/session tuple. Reusing a session across tasks/runs is rejected. Duplicate step IDs are rejected before dispatch.
- Receipts persist correlation IDs, timestamps, action, URL, command metadata, exit status, output hashes and artifact paths. Page output is returned to the caller but is not copied into the receipt ledger.
- Commands use argument arrays with `shell=False`. Credential selectors are rejected; cookies, auth state, arbitrary JavaScript, uploads and downloads are not exposed in this initial slice.

**Recovery boundary:** local session metadata and action receipts survive process restarts while the workspace survives. The browser daemon itself is not proven recoverable after a GitHub Actions job/runner is destroyed. Never describe this as persistent cross-job browser continuity.

**Execution boundary:** GitHub Actions provides an ephemeral Linux host for controlled acceptance tests. It is not a durable authenticated browser service, and the adapter is not directly callable from the current ChatGPT session. Real browser capability remains PARTIAL until the browser workflow passes and a supported dispatch/result path is proven.
