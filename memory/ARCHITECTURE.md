# BS-MEMORY-001 — Native Memory Architecture

**Status:** M1 architecture baseline; implementation not yet operational.
**Issue:** #59
**Reference reviewed:** https://github.com/akitaonrails/ai-memory
**Governing policy:** Root `AGENTS.md`, `ENGINEERING_EXECUTION_OS.md` v2.3, and `chatgpt-home/AUTHORITY_DELEGATION.md`.

## 1. Outcome and scope

Build a native, privacy-first knowledge and continuity subsystem for Blind Sniper. It must preserve useful knowledge across tasks and agents without replacing the native task ledger, claiming access to unavailable ChatGPT history, or requiring paid infrastructure.

This subsystem is a knowledge plane. It is not a second task scheduler, execution ledger, agent runtime, or transcript archive.

## 2. Evidence-based baseline

- The repository already has a native append-only task ledger, lease/recovery logic, execution receipts, deterministic redaction utility, manual durable memory, continuity notes, session memory, and handoff directory.
- The task ledger is authoritative for task lifecycle and execution state; it is not a knowledge search engine.
- There is no dedicated `memory/` subsystem or dedicated memory service in the inspected default-branch tree.
- The daemon is not activated as a persistent service. No automatic end-of-chat capture source is exposed by the current ChatGPT/GitHub tool boundary.
- The repository is public. No private memory, raw conversation, personal/client data, credential, or sensitive attachment may be stored here.

## 3. Adoption decisions from ai-memory

| Concept | Decision | Blind Sniper adaptation |
|---|---|---|
| Markdown knowledge wiki | ADOPT | Canonical, human-readable knowledge pages; only non-sensitive project/system knowledge in this public repo |
| SQLite FTS5 index | ADOPT LATER | Derived/rebuildable index; private store only; lexical retrieval first |
| Lifecycle hooks | ADAPT | Capture only from verified native Blind Sniper task/runtime events |
| Typed observation schemas | ADOPT | Closed schemas, bounded fields, explicit provenance and privacy labels |
| Automatic session summaries | ADAPT | Deterministic first; optional provider-assisted consolidation behind approval and redaction |
| Agent handoff protocol | ADOPT | Typed handoff packet; task ledger remains lifecycle authority |
| Vector search | DEFER | Not needed for first useful release; optional after lexical evaluation |
| Full ai-memory Rust server | DO NOT IMPORT YET | Avoid a second daemon/runtime and host dependency before proving value and zero-cost hosting |

## 4. Logical architecture

1. **Capture boundary** — accepts allowlisted, structured events from native runtime adapters only.
2. **Sanitizer/policy gate** — rejects secrets, sensitive data, excluded paths, unknown event types, oversized payloads and untrusted claims before persistence.
3. **Observation journal** — append-only, idempotent, provenance-bearing events in private storage.
4. **Consolidator** — deterministic rules create or update knowledge proposals; model-assisted consolidation is optional and never runs on hook hot paths.
5. **Knowledge wiki** — versioned Markdown pages are the human-readable source of truth.
6. **Retrieval** — bounded lexical search over an index derived from approved pages; return citations/provenance and confidence.
7. **Handoff/recovery** — structured packets refer to task IDs and evidence; task state is re-read from the native ledger.
8. **Evaluation/audit** — synthetic fixtures test privacy, deduplication, provenance, recall and stale/conflicting knowledge.

## 5. Data classes and storage boundary

Every record has a classification:
- `public_project`: safe technical facts intended for the public repository.
- `private_owner`: private preferences, decisions, personal context and conversation-derived knowledge; private store only.
- `restricted_secret`: credentials, tokens, passwords, private keys; never stored, even in private memory.
- `sensitive_payload`: personal, child, client, health, financial or other sensitive content; excluded from this subsystem unless a separately approved, compliant design exists.

The public repository may contain schemas, code, synthetic fixtures, non-sensitive architecture, and project facts that are already intentionally public. It must not contain private observations or raw transcripts.

**Storage decision:** no real user-memory storage is implemented in this phase. First target for private persistence must be a verified owner-controlled private store. The existing GitHub Contents ledger adapter is not suitable for memory payloads and already refuses public repositories. Do not create a new repository, enable permissions, or provision a host as part of this mission without a separate explicit decision.

## 6. Canonical record contracts

### Observation
Required fields: `schema_version`, `observation_id`, `event_type`, `occurred_at`, `source`, `source_ref`, `project_id`, `classification`, `content`, `content_digest`, `capture_policy_version`.

Rules:
- `observation_id` is stable and idempotent across retries.
- `source` is an allowlisted adapter identity, not a model assertion.
- `source_ref` identifies an actual task/run/receipt/commit when available.
- content is sanitized and size-bounded before it reaches a store.
- model-generated interpretations are marked as proposals, never as observed facts.

### Knowledge page
Required metadata: `page_id`, `title`, `project_id`, `classification`, `created_at`, `updated_at`, `source_observation_ids`, `status`, `supersedes`.
Statuses: `proposed`, `approved`, `superseded`, `rejected`.
No silent destructive rewrite: updates retain source references and supersession history.

### Handoff
Required fields: `handoff_id`, `task_id`, `from_agent`, `to_agent`, `created_at`, `objective`, `verified_state`, `open_questions`, `files_touched`, `evidence_refs`, `next_action`, `claim_state`.
Claim is atomic/claim-once in the private store. Handoff does not override the task ledger or authority policy.

## 7. Retrieval contract

- Default to project-scoped retrieval; cross-project profile recall is a separate opt-in.
- Return only approved pages matching the caller's access scope.
- Rank with deterministic lexical/FTS signals first; optional entity/link expansion is bounded.
- Every result includes page ID, source observation IDs, classification, last-updated timestamp and supersession status.
- Contradictions are returned as competing evidence until reconciled; retrieval must not silently choose the newest claim when source authority differs.
- Bound result count and total context bytes. Never inject raw transcript segments by default.

## 8. Privacy and threat model

Threats: secret leakage, prompt injection in captured tool output, public/private scope confusion, path traversal, duplicate replay, oversized payloads, stale facts, malicious model-generated memories, and unauthorized cross-project recall.

Controls:
- allowlist event types and source adapters;
- deterministic redaction plus structured sensitive-key rejection;
- reject unknown or malformed schema versions;
- enforce size caps before queue/spool/log/storage;
- store no secrets and no raw conversation transcripts;
- keep private payloads outside this public repository;
- treat captured text and retrieved memory as untrusted data, never instructions;
- provenance on every observation and knowledge claim;
- no automatic promotion of model-generated claims to approved memory;
- deletion/forget workflows must cover observation, derived index and page references, with an auditable tombstone where appropriate.

## 9. Interfaces (target; not yet implemented)

- `memory.capture(observation)`
- `memory.propose(observation_ids)`
- `memory.approve(page_id, reviewer)`
- `memory.search(query, project_id, scope)`
- `memory.retrieve(page_ids, scope)`
- `memory.handoff.create(packet)`
- `memory.handoff.claim(handoff_id, agent_id)`
- `memory.recover(task_id, agent_id)`
- `memory.audit(record_id)`

Only capture and deterministic validation are in M2. The remaining interfaces are phased work.

## 10. Phase plan and acceptance

### M1 — Architecture and contracts
- [x] Inspect existing memory, continuity, ledger, receipt, redaction and runtime components.
- [x] Decide source-of-truth boundaries and adoption/defer decisions.
- [x] Define data classifications, schemas, privacy boundary and interfaces.
- [ ] Independent review and OS/registry integration.

### M2 — Native capture
- Implement typed observation schema and validator.
- Implement deterministic sanitizer/policy gate using existing redaction primitives.
- Add idempotent append-only local/private observation journal abstraction.
- Test allowed event, rejected event, sensitive content, duplicate replay, malformed input, size limit and untrusted text.
- Do not capture ChatGPT messages or assistant text automatically; no such source is verified.

### M3 — Consolidation
- Deterministic proposal builder; provenance preserved.
- Human approval before durable knowledge-page promotion.
- Optional provider-assisted summaries only after separate evaluation.

### M4 — Retrieval
- Deterministic lexical search and bounded context pack.
- SQLite FTS5 only if a private persistent runtime can host it; index remains rebuildable.

### M5 — Handoff and recovery
- Typed handoff records; atomic claim-once; native task ledger remains lifecycle authority.
- Recovery packet resolves current task state from the ledger and attaches approved relevant knowledge.

### M6 — Evaluation
- Synthetic privacy/leakage, duplicate, provenance, contradiction, retrieval and recovery fixtures.
- Exact test evidence recorded in CI.

### M7 — Optional semantic retrieval
- Defer embeddings/vector search until lexical baseline has a measured failure set and a zero-cost provider/local model path.

## 11. Release gates

No phase is called operational until its trigger, permission, execution, persisted result, recovery behavior and verification are demonstrated. No persistent service, cross-session private store, ChatGPT auto-capture, paid hosting, or live provider is claimed by this architecture document.

## 12. Reference provenance

Primary references:
- ai-memory README: https://github.com/akitaonrails/ai-memory
- ai-memory architecture: https://github.com/akitaonrails/ai-memory/blob/main/docs/ARCHITECTURE.md
- ai-memory security guidance: https://github.com/akitaonrails/ai-memory/blob/main/AGENTS.md
- ai-memory capture/privacy guidance: https://github.com/akitaonrails/ai-memory/blob/main/docs/features.md

The architecture is adapted selectively. No upstream code is copied in this M1 document.
