# Blind Sniper — Advanced Master Build Plan

**Status:** PLAN / EXECUTION BACKLOG — implementation has not started under this plan  
**Date:** 2026-11-26  
**Governing policy:** `/ENGINEERING_EXECUTION_OS.md` v2.3 and `/AGENTS.md`  
**Baseline:** `main` at `f9cde15b20f9aaac6095eb45e727da0dbdee3104` when this plan was prepared  
**Source audit:** Issue #79, including the main audit, four appendices and final capability matrix  
**Scope:** `madnessgate44-debug/Blind-sniper-` only

> This document is an execution specification, not evidence that the listed capabilities exist. The Issue #79 findings are audit-reported unless independently re-verified during the relevant ticket. Every ticket must update evidence from the live repository and must not inherit an earlier claim as proof.

## 1. Product outcome

Build Blind Sniper as a standalone, owner-operated autonomous coding and research system. It must own task state, orchestration, agent lifecycle, execution, browser sessions, memory, permissions, recovery and reporting. A model provider supplies inference only; it does not own task state or orchestration.

The owner must be able to submit a task, observe progress, approve gated actions, inspect evidence and receive a durable result from a phone.

### Explicit architecture boundaries

- **Allowed runtime dependency:** model-provider interface for inference (including configurable compatible providers).
- **Not runtime dependencies:** OpenHands, Forge/Firstborn, Instinct, their APIs, MCP servers, sessions, workers, browsers, issue-mention triggers, or return paths.
- **Native replacements:** Blind Sniper owns its agent runtime, durable queue/ledger, worker, executor, tool registry, browser lifecycle, memory, supervisor, notifications and owner interface.
- **Source of truth:** this repository and its verified runtime state.
- **Privacy:** no private memories, raw transcripts, personal/client data, curriculum files, credentials, tokens or secret values in this public repository.
- **Cost boundary:** no paid service, subscription, paid compute or card use without separate owner authorization. Prefer free/local/self-hostable options, but do not misrepresent free-tier limits or reliability.

## 2. Current audit baseline — reported, not accepted as final proof

Issue #79 reports a substantial Python runtime foundation (roughly 22 modules / 7,950 lines and 33 test files), including task queue/ledger, worker, model worker, executor, tool runtime, browser adapter, memory modules, watcher, daemon and redaction. The audit also reports:

- Vercel health endpoint returned HTTP 200 while task execution was disabled and the worker was not activated.
- No verified resident production worker, live production task execution, owner notifications, ChatGPT-facing invocation endpoint, authenticated Google/WhatsApp connectors, or private durable-store round trip.
- One synthetic remote model invocation was completed; this is not proof of multi-agent autonomy or production operation.
- A local Qwen/llama.cpp proof and mutation experiment were LOCAL ONLY and not merged into `main`.
- REE was used through a manually dispatched wrapper around a pinned third-party repository; it was not integrated as a native task lifecycle capability. The successful workflow allowed a benchmark exit code of 1 and only validated fixture rows; blocked native-provider rows remain unproven.
- Independent multi-agent execution, durable worker recovery, production browser lifecycle, private memory, continuous supervision and end-to-end unattended autonomy were not established.
- A local connector-registry branch was not merged and used fake HTTP only.
- Some modules and related repositories were only partially inspected by the audit author.
- The reported clean-clone suite had three environment/browser errors under Python 3.10.12; a clean Python 3.11+ rerun was not reported.
- Repository continuity documents were reported stale.

**Acceptance rule:** re-run and inspect every relevant claim. Do not treat this summary as current implementation truth or as a substitute for reading source, tests, workflows, deployment configuration and logs.

## 3. Delivery sequence and gates

| Gate | Tickets | Exit condition |
|---|---|---|
| G0 — Truth baseline | BS-001 | Current architecture, files, dependencies, branch/PR state and evidence gaps mapped |
| G1 — Native core | BS-002, BS-003, BS-004 | External orchestration dependencies isolated; provider contract and real agent runtime proven |
| G2 — Durable operation | BS-005, BS-006 | Recoverable task lifecycle and native execution path proven |
| G3 — Real-world tools | BS-007, BS-008 | Browser and private memory/security proven |
| G4 — Autonomy | BS-009 | Supervisor safely runs bounded multi-step work and recovers from failure |
| G5 — Product acceptance | BS-010, BS-011 | End-to-end acceptance evidence and deployable owner interface/worker |

Do not start downstream implementation based on guessed interfaces. BS-001 establishes the actual file-level plan; tickets may be split or reordered only with documented dependency reasoning and no scope loss.

---

# 4. Execution tickets

## BS-001 — Final Architecture and Code Inventory

**Priority:** P0 · **Type:** Read-only inspection · **Gate:** G0

### Objective
Establish the real current state of Blind Sniper and produce a file-level architecture map before modifying runtime code.

### Required work
1. Read `AGENTS.md`, `ENGINEERING_EXECUTION_OS.md` v2.3, `chatgpt-home/AUTHORITY_DELEGATION.md`, `chatgpt-home/BLIND_SNIPER.md`, `chatgpt-home/CURRENT_STATE.md`, and `chatgpt-home/runtime/BUILD_PROGRESS.md`. Report any missing/unreadable file as a blocker.
2. Record current default branch, HEAD SHA, open PRs, relevant branches, workflow state and deployment/health state where tools permit.
3. Enumerate all runtime modules, entry points, workflow files, tests, manifests, deployment files and docs. Read the relevant source; label partial inspection explicitly.
4. Trace real call paths for provider invocation, agent dispatch, task enqueue/claim/lease, ledger writes, worker loop, executor dispatch, tool permissions, browser operations, memory reads/writes, supervisor/watcher and health endpoints.
5. For each capability, classify: implemented and exercised; implemented but fixture-only; partial; dead/unwired; absent; or unknown.
6. Identify external runtime dependencies and code paths that violate the standalone boundary, especially Forge/Firstborn references and third-party browser/REE wrappers.
7. Reconcile stale state docs only after the evidence inventory is complete.

### Deliverables
- `docs/architecture/CURRENT_RUNTIME_MAP.md`
- `docs/architecture/CAPABILITY_EVIDENCE_MATRIX.md`
- Updated `chatgpt-home/CURRENT_STATE.md` and `chatgpt-home/runtime/BUILD_PROGRESS.md` if the inspected facts require it.

### Acceptance criteria
- Every listed runtime capability maps to concrete source files, trigger path, tests and evidence status.
- Every external dependency is classified as inference-only, build/test-only, runtime dependency, or documentation-only.
- No unsupported production/autonomy claim remains in the current-state docs.
- Inspection limitations and unverified deployment state are explicit.
- No application/runtime behavior is changed by this ticket.

### Verification
Review the generated maps against actual source paths and current GitHub state. This ticket is complete only when the inventory is internally consistent and reviewable.

---

## BS-002 — Native Dependency Isolation and Forge Removal

**Priority:** P0 · **Type:** Architecture/runtime repair · **Depends on:** BS-001

### Objective
Make Blind Sniper independent of Forge/Firstborn, OpenHands and Instinct at runtime.

### Required work
1. Use BS-001 evidence to enumerate every import, subprocess, URL, workflow, environment variable, callback, artifact contract and task route involving those systems.
2. Separate provider inference from orchestration. Provider adapters may send inference requests and receive model output only.
3. Replace runtime calls to external coding agents, external workers, issue-mention triggers, external browser/session APIs and return routes with native interfaces.
4. Replace any Forge-specific executor/patch verification route with a Blind Sniper-owned patch verification contract and tests.
5. Remove or quarantine obsolete workflows and dead integration code only when no required native path depends on them; document removals.
6. Ensure no hidden fallback silently delegates tasks to external systems.

### Deliverables
- Native boundary/dependency map.
- Updated runtime code and tests.
- Explicit list of removed, retained and documentation-only references.

### Acceptance criteria
- Static dependency scan finds no forbidden external orchestration/runtime import or invocation in production paths.
- A controlled task can reach the native runtime without contacting OpenHands, Forge/Firstborn or Instinct.
- Provider adapter is limited to inference and cannot mutate task state.
- Native replacement tests pass; no regression in unrelated accepted behavior.

### Verification
Inspect diff and dependency scan output; run targeted tests and one bounded end-to-end native-trigger test. Documentation references may remain when clearly historical and non-executable.

---

## BS-003 — Model Provider Interface and Inference Contract

**Priority:** P0 · **Type:** Runtime foundation · **Depends on:** BS-001, BS-002

### Objective
Create a stable provider boundary that supplies model inference without owning orchestration or durable state.

### Required work
1. Define provider request/response schemas, streaming behavior, timeout, cancellation, token/usage metadata, structured output, tool-call representation and error taxonomy.
2. Support explicit provider/model selection and configurable fallback policy. Fallback must be visible in task receipts.
3. Keep credentials in a private runtime secret source; never commit or log secret values.
4. Implement retry/backoff and rate-limit handling with bounded budgets and idempotency safeguards.
5. Add deterministic fake-provider tests plus a separately labeled live smoke test when credentials/free endpoint are actually available.
6. Record model identity, provider, request correlation ID, timing, usage and sanitized outcome in the task evidence receipt.

### Deliverables
- Provider interface/schema.
- At least one maintained adapter and deterministic test adapter.
- Contract tests and provider smoke workflow/report.

### Acceptance criteria
- Runtime can swap providers without changing queue, task, agent or executor code.
- Provider failures do not corrupt task state or create duplicate side effects.
- Tests prove malformed response, timeout, rate limit, cancellation and fallback behavior.
- A live call is labeled as such and never conflated with fixture tests.

---

## BS-004 — Independent Native Agent Runtime

**Priority:** P0 · **Type:** Core orchestration · **Depends on:** BS-003

### Objective
Implement independently scheduled agents with isolated context, scoped tools and explicit handoffs.

### Initial agent roles
Planner, Researcher, Architect, Builder, Tester, Reviewer and Supervisor. These are role definitions, not proof of capability; each must have a real trigger and execution contract.

### Required work
1. Define agent registry schema: stable ID, role, model policy, system contract, tool allowlist, permissions, budgets, timeout and output schema.
2. Implement agent invocation through BS-003 with separate context windows and explicit task-scoped inputs.
3. Implement delegation/handoff contracts: parent task, child task, objective, inputs, acceptance criteria, evidence and return status.
4. Prevent agents from reading unrelated task/private memory unless authorized by policy.
5. Record independent agent runs, inputs, outputs, tool calls and receipts.
6. Add supervisor-controlled concurrency limits, cancellation and budget enforcement.

### Deliverables
- Native agent registry and dispatcher.
- Versioned agent profiles and schema validation.
- Multi-agent integration tests and traceable handoff receipts.

### Acceptance criteria
- At least three distinct agents execute one bounded task through the native trigger with isolated contexts and different scoped permissions.
- Each handoff is persisted and traceable to its parent.
- An unauthorized tool request is denied and recorded.
- Agent labels alone do not satisfy acceptance; actual run receipts and outputs are required.

---

## BS-005 — Durable Task Lifecycle, Queue and Recovery

**Priority:** P0 · **Type:** Reliability foundation · **Depends on:** BS-001, BS-004

### Objective
Guarantee durable task state and safe recovery across worker/process interruption.

### Required work
1. Define task state machine, allowed transitions and terminal states.
2. Implement durable queue, ledger, lease/heartbeat, worker ownership and stale-lease recovery.
3. Add bounded retries, exponential backoff, timeout, cancellation and dead-letter handling.
4. Add idempotency keys and side-effect checkpoints to prevent unsafe duplicate execution.
5. Persist task inputs, agent handoffs, tool receipts, checkpoints, outputs and failure diagnostics.
6. Make storage backend configurable and suitable for private durable production storage; GitHub Contents API may not be treated as a production database without an explicit load/concurrency/security justification.
7. Define backup, retention and corruption-recovery behavior.

### Deliverables
- State machine and durable storage contract.
- Worker lifecycle and recovery implementation.
- Failure-injection tests and operational runbook.

### Acceptance criteria
- Kill a worker during a controlled task, restart it, and prove correct resume from the last safe checkpoint.
- Concurrent workers cannot claim the same lease unsafely.
- Retry does not duplicate a non-idempotent side effect.
- Ledger integrity and task/receipt identity are validated on recovery.

---

## BS-006 — Native Executor and Tool Runtime

**Priority:** P0 · **Type:** Execution engine · **Depends on:** BS-002, BS-004, BS-005

### Objective
Give agents a native, permissioned way to inspect and modify workspaces and run engineering tools.

### Required work
1. Define a tool registry with schemas, permissions, input validation, timeouts, output limits and audit receipts.
2. Implement workspace operations: list/read/search files, create/update files, apply patches, inspect diffs and manage Git branches/commits.
3. Implement allowlisted test/build/lint commands in an isolated execution environment.
4. Add approval gates for destructive, external, privileged or high-impact operations.
5. Add path traversal protection, workspace isolation, resource limits and safe subprocess handling.
6. Replace all Forge-specific verification with native diff, patch and test verification.
7. Ensure every action emits a durable, redacted receipt linked to task and agent IDs.

### Deliverables
- Native executor and tool registry.
- Workspace isolation and command policy.
- Patch verification, permission and failure tests.

### Acceptance criteria
- A bounded task inspects a real repository, changes an authorized file, runs its test, and returns an inspectable diff plus receipts.
- An unauthorized path or command is denied.
- A simulated timeout/crash leaves recoverable state and no false success.
- No tool can bypass the task permission policy.

---

## BS-007 — Native Browser Runtime

**Priority:** P1 · **Type:** Tool runtime · **Depends on:** BS-005, BS-006

### Objective
Provide a Blind Sniper-owned browser lifecycle rather than relying on an external agent's browser/session.

### Required work
1. Define browser session lifecycle, ownership, isolation, persistence, cleanup and recovery.
2. Implement navigation, DOM/accessibility inspection, interaction, screenshot, download and upload operations through a native tool contract.
3. Enforce domain allowlists, navigation policy, download restrictions and explicit approval for sensitive actions.
4. Integrate browser operations with task leases, receipts, cancellation and recovery.
5. Prevent cookie/session leakage between tasks and agents; keep credentials in secure storage.
6. Select a browser engine/hosting approach based on verified compatibility, security, persistence and no-cost constraints. Do not assume Vercel functions can host a resident browser worker.

### Deliverables
- Native browser adapter/session manager.
- Browser permission policy and operational runbook.
- Real-browser integration tests.

### Acceptance criteria
- A real authorized site interaction is performed through Blind Sniper's own task/tool path.
- Session ownership, screenshots/DOM evidence and action receipts are inspectable.
- Cross-task session leakage and unauthorized-domain navigation tests are denied.
- Worker interruption behavior is documented and tested.

---

## BS-008 — Private Memory, Identity and Credential Security

**Priority:** P0 · **Type:** Security/data layer · **Depends on:** BS-005

### Objective
Implement private durable memory and secure identity/credential handling without exposing personal data in the public repository.

### Required work
1. Define memory scopes: owner, project, task, agent and session; specify retention, provenance and deletion behavior.
2. Implement a private persistent store with encryption in transit/at rest where supported, access controls and backup/recovery.
3. Implement a credential vault/secret-provider interface, token refresh and revocation where applicable.
4. Add role-based access control, least privilege, secret redaction and audit events.
5. Prevent private memory and credentials from entering prompts, logs, artifacts or public Git history unless explicitly authorized and appropriately minimized.
6. Keep connector integration optional and policy-controlled; no connector is considered authenticated until a real authorization flow and live request are verified.

### Deliverables
- Memory and credential architecture.
- Private-store adapter and security tests.
- Data classification, retention and incident runbook.

### Acceptance criteria
- Live private-store write/read round trip succeeds under the intended identity.
- Unauthorized agent/task access is denied.
- Secret scanning and redaction tests prove secret values do not appear in logs/receipts.
- Backup and deletion behavior are tested and documented.
- No private user data is committed to this public repository.

---

## BS-009 — Autonomous Supervisor, Scheduler and Recovery

**Priority:** P0 · **Type:** Autonomy control plane · **Depends on:** BS-004, BS-005, BS-006, BS-008

### Objective
Run bounded unattended work safely, continuously, and recoverably under explicit owner policy.

### Required work
1. Implement a persistent supervisor loop with durable scheduling and task prioritization.
2. Define autonomy levels and policy gates: observe, propose, execute reversible actions, request approval for sensitive actions.
3. Add health monitoring, worker heartbeat, queue age, stuck-task detection, retry/recovery and escalation.
4. Add budgets for model usage, wall-clock time, tool calls, concurrency and resource consumption.
5. Add stop/pause/resume controls and emergency kill switch.
6. Generate owner-facing summaries with completed work, evidence, failures, approvals needed and remaining risks.
7. Implement notification interface only after delivery channel credentials and privacy policy are configured and verified.

### Deliverables
- Supervisor/scheduler service.
- Autonomy policy and safety controls.
- Failure/recovery tests and operator runbook.

### Acceptance criteria
- A bounded sequence of multiple tasks runs without continuous user prompting.
- Injected agent/provider/worker failures trigger safe recovery or escalation, not silent success.
- Budgets and autonomy policy are enforced.
- Owner can pause execution and verify that no new task is claimed.
- Notifications are marked unconfigured until a real end-to-end delivery is proven.

---

## BS-010 — End-to-End Acceptance Harness and Evidence Ledger

**Priority:** P0 · **Type:** Verification · **Depends on:** BS-003 through BS-009

### Objective
Create repeatable acceptance tests that prove the complete system path rather than isolated modules or fixture-only behavior.

### Required work
1. Define one canonical end-to-end scenario: owner submits task → supervisor plans → multiple agents collaborate → executor changes a test workspace → tests run → reviewer checks diff → result/receipt persists → owner receives status.
2. Add fault injection for provider outage, malformed output, worker kill, lease expiry, duplicate delivery, tool denial, browser failure and storage outage.
3. Separate unit, fixture, integration, live-provider, live-browser and production-smoke test categories.
4. Require each verification ledger entry to contain exact action/command, exit code/result, raw output excerpt, timestamp and artifact reference.
5. Make skipped tests visible and prevent skipped/fixture tests from being reported as full end-to-end acceptance.
6. Add security/privacy checks and dependency-boundary scans.

### Deliverables
- End-to-end harness and test matrix.
- Verification ledger format and sample evidence bundle.
- CI workflows with honest pass/skip/fail semantics.

### Acceptance criteria
- Canonical scenario completes through the actual native trigger and produces persisted receipts/artifacts.
- Fault-injection tests demonstrate safe failure and recovery.
- CI cannot pass the acceptance gate when required live/integration checks are silently skipped or their failures are masked.
- Every claimed capability maps to a reproducible test and evidence artifact.

---

## BS-011 — Production Hosting, Owner Interface and Operations

**Priority:** P1 · **Type:** Productization · **Depends on:** BS-005, BS-008, BS-009, BS-010

### Objective
Make the system usable and observable by the owner from a phone, with a persistent worker and secure operational controls.

### Required work
1. Define deployment topology separating stateless API/UI from persistent worker, scheduler, browser and private data store.
2. Evaluate existing GitHub/Vercel options and other zero-cost/self-hostable options against actual process-lifetime, storage, networking, security and quota constraints.
3. Do not deploy or introduce paid infrastructure without explicit authorization.
4. Build a responsive owner interface for task submission, status, logs, approvals, receipts, pause/resume and failure reporting.
5. Add authentication, authorization, rate limits, audit logs, health/readiness endpoints and operational metrics.
6. Add backup/restore, migration, rollback and incident procedures.
7. Verify deployment using real runtime behavior; HTTP 200 health alone is not proof of task execution.

### Deliverables
- Deployment architecture and cost/limit record.
- Responsive owner UI/API.
- Persistent worker deployment and operations runbook.

### Acceptance criteria
- Owner can submit, monitor, approve and inspect a completed task from a phone.
- Worker remains active across API requests and recovers after process restart.
- Production smoke test proves a real task execution and durable result.
- No paid service or spend is introduced without separate owner approval.
- Health, readiness and task-execution status are distinct and truthful.

---

# 5. Mandatory ticket execution protocol

Every ticket executor must:

1. Start with the OS TOOL DECLARATION and finish with its COMPLIANCE HEADER.
2. Re-read governing instructions and inspect live repository state before implementation.
3. Convert the ticket into numbered requirements (R1, R2, …), each with measurable acceptance criteria.
4. Record exact files to inspect/change and dependencies before editing.
5. Work on a feature branch and keep the diff scoped to the ticket.
6. Run relevant checks and preserve raw outputs/evidence; no fabricated verification ledger entries.
7. Inspect the resulting diff, security/privacy implications, regressions and current PR/commit state.
8. Report blockers and unknowns explicitly. Do not mark a ticket complete because code was generated or a workflow was green.
9. Do not merge or deploy until the relevant acceptance gate passes.
10. Keep all external-agent integrations out of Blind Sniper's runtime architecture. A human may use a coding assistant to contribute changes, but the product itself must remain standalone.

### Ticket report template

```text
TICKET ID:
STATUS: REQUESTED | STARTED | COMPLETED | VERIFIED | BLOCKED
BASE SHA:
BRANCH / PR:
OBJECTIVE:
REQUIREMENTS AND ACCEPTANCE:
FILES INSPECTED:
FILES CHANGED:
DEPENDENCIES:
SECURITY / PRIVACY:
VERIFICATION LEDGER:
DIFF REVIEW:
FAILURES / BLOCKERS / UNKNOWNS:
NOT RUN / OUT OF SCOPE:
ROLLBACK:
NEXT GATE:
```

## 6. Evidence vocabulary

Use the repository OS v2.3 vocabulary exactly: `[V]` verified by direct tool evidence, `[C]` reported claim, `[I]` inference, `[A]` assumption, `[U]` unknown, `[B]` blocker. In user-facing summaries, the shorter labels `[VERIFIED]`, `[HYPOTHESIS]`, `[UNPROVEN]` and `[FAILED]` may be added, but they must not replace the OS tags in repository execution records.

## 7. First authorized action

Start with **BS-001 only**. It is read-only and produces the evidence baseline. Do not begin BS-002 or runtime implementation until BS-001 has been reviewed and the actual dependency map is available.

## 8. Global definition of done

Blind Sniper is not considered complete or autonomous until the canonical end-to-end scenario passes through the native trigger, independent agents, durable task lifecycle, native executor/tools, private storage, supervisor and persistent worker; the owner can inspect the receipts and control execution; failure/recovery and security tests pass; and production task execution is demonstrated with real runtime evidence.

A green unit-test suite, a health endpoint, a single provider smoke call, a fixture benchmark, a local-only experiment, a draft PR or a plan document is not sufficient.
