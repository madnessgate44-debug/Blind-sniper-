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
| OpenHands Cloud V1 API (optional, disabled) | `scripts/blind_sniper_openhands_cloud.py` | Contract-tested (fake transport); no live round trip | Events/messages via API | PARTIAL |
| Forge MCP (Streamable HTTP, optional, disabled) | `scripts/blind_sniper_forge_mcp.py` | Disabled: no durable endpoint + auth configured | MCP tool results | BLOCKED |
| Codex CLI | Host invocation | Host runtime required | Local filesystem/worktree | NOT AVAILABLE HERE |

Blind Sniper is native-first and self-contained (see `chatgpt-home/BLIND_SNIPER.md`,
`BLIND_SNIPER_OS.md` and `AUTONOMY_PROTOCOL.md`). The two client modules below are **optional
adapters, not dependencies**: neither is wired into any profile or workflow, neither is invoked by
the native runtime, and both refuse to operate unless explicitly configured. They exist to satisfy
issue #46's request for a real V1 client and an MCP transport, and to hold that work behind a
disabled gate. Enabling either is an Owner decision, and doing so would not make it a prerequisite
for native operation.

### OpenHands Cloud V1 client (optional)

`scripts/blind_sniper_openhands_cloud.py` implements the documented V1 surface:
`POST /api/v1/app-conversations` (start), `GET /api/v1/app-conversations/start-tasks?ids=`
(poll to READY), `GET /api/v1/app-conversations?ids=` (status),
`GET /api/v1/conversation/{id}/events/search` (messages, paginated by `page_id`) and a
best-effort `POST /api/v1/app-conversations/{id}/cancel`. Bearer auth is read from
`OPENHANDS_CLOUD_API_KEY`; the token is never printed, logged or committed. Every surface is
redacted through `scripts/blind_sniper_redact.py`. The adapter is contract-tested with a fake
transport (`tests/test_blind_sniper_openhands_cloud.py`) and remains PARTIAL until a real
authenticated round trip is performed.

### Forge MCP client (optional)

`scripts/blind_sniper_forge_mcp.py` implements the MCP Streamable HTTP transport (JSON-RPC 2.0
`initialize` / `tools/list` / `tools/call`) with bearer auth, a host tool allowlist, per-call
timeouts and redacted audit receipts. It is disabled by default and refuses to construct unless
a durable HTTPS endpoint and auth token are configured; ephemeral sandbox hosts are refused and
browser write tools require an explicit host approval reference. It is contract-tested
(`tests/test_blind_sniper_forge_mcp.py`) and stays BLOCKED until a durable endpoint, auth and a
real round trip exist. This module does not register or claim a ChatGPT connector.

### Durable queue and worker (native)

`scripts/blind_sniper_worker.py` implements a queue protocol over the native ledger:
enqueue → exclusive claim → lease/heartbeat → bounded retry → complete/fail → cancel, plus
stale-lease recovery and reconciliation. Every mutation runs through `append_guarded`, so the
read-decide-append sequence is atomic under the ledger file lock (local) or GitHub blob-SHA CAS
(private remote). Only payload digests are stored; private task payloads and continuity stay out
of the public repository. `scripts/blind_sniper_autonomy.py` performs one bounded pass
(recover → drain → health → digest) and refuses unattended activation until the executor, data
store and notification prerequisites are all configured. This is a protocol, not a background
daemon; no scheduler is claimed.



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
