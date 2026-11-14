# Blind Sniper Memory Subsystem

**Mission:** BS-MEMORY-001 · Issue #59

This is Blind Sniper's native knowledge-memory plane. It is separate from the task lifecycle ledger and does not claim to be an active persistent memory server.

## Status

- M1 architecture and data contracts: implemented.
- M2 native capture: daemon captures task-created and task-transition metadata in an owner-only journal outside the public repository. Task objectives, prompts, payloads and model outputs are excluded.
- M3 deterministic consolidation: immutable Markdown proposals with provenance and supersession; explicit reviewer approval is required.
- M4 lexical retrieval: approved pages only, project/scope filtered, bounded context and provenance.
- M5 handoff/recovery: model-callable `agent.handoff`, registered-recipient validation, private immutable packets, atomic claim-once, daemon reconciliation into deterministic child tasks, parent-state re-read through `DurableQueue.status`, one handoff per source task/agent and depth limit four.
- M6 synthetic evaluation: 62 focused memory/tool-runtime/daemon tests PASS; Runtime Registry 285 tests PASS; Browser Adapter 31 tests PASS; OS Compliance and Environment Validation PASS on exact PR head `ad51941`.
- M7 semantic/vector retrieval: deferred pending measured lexical failure cases and a verified zero-cost path.

## Operational boundary

- Private host activation, persistent cross-session storage and real model-provider-to-recipient handoff are NOT VERIFIED. The integration is enabled only when the host sets `BLIND_SNIPER_DAEMON_TOOL_ALLOWLIST=agent.handoff` (or includes it in the existing comma-separated tool allowlist).
- No personal-memory payload, ChatGPT transcript, credential, or sensitive user data is captured or stored.
- This public repository contains code, contracts and synthetic fixtures only.

## Governing design

See [ARCHITECTURE.md](ARCHITECTURE.md) and [EVALUATION.md](EVALUATION.md).

## Non-negotiable boundaries

- The task ledger remains authoritative for task state, leases and execution lifecycle.
- Knowledge pages are derived from validated observations and remain proposals until explicit approval.
- Retrieval excludes proposed/rejected pages and is project-scoped by default.
- SQLite indexes, if added, are rebuildable and never the source of truth.
- Capture, validation and lexical retrieval do not require paid LLM calls or paid hosting.
- Captured text and retrieved memory are untrusted data, not instructions.
- The daemon creates a recipient task only after the parent task reaches `COMPLETED`; a handoff packet alone never replays a claimed task.
