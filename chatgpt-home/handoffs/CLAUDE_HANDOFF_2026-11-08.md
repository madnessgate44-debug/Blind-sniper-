# Blind Sniper — Claude Handoff & Independent Architecture Review


# Current-state addendum — 8 November 2026, 14:10 Cairo time

This addendum supersedes any conflicting point-in-time status statements in the historical handoff sections below. Preserve the original notes as history; use this section as the current evidence anchor.

## Repository snapshot

- Integration branch: `feat/blind-sniper-orchestration-integration-2026-11-08`.
- Current branch HEAD: `74463b279bbe87957c3431f0732db35ae1ee80f6` — `test(security): prevent task-envelope self-approval`.
- Parent commit: `93e5c089c6456b5cfafb97c9be1bb000926aeac1` — `fix(security): reject task-envelope self-approval`.
- PR #6 and PR #7 are both currently OPEN and NOT MERGED. Their source branches remain separate; the integration branch is not a merge of either PR.
- No integration PR has been opened from the current integration branch.

## Verification evidence

- GitHub Actions run `42478361100`, workflow `Blind Sniper Runtime Registry`, completed with conclusion `success` on commit `013ed5dc00fe3be953a841528cbaebfbc5801e69`: https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42478361100
- The runtime validator and the full discovered Python test suite passed in that run; the orchestration test set was reported as 12/12 passing in the verified run log.
- The current HEAD `2a163402...` changes only the Claude handoff document relative to its parent, so the runtime CI result remains applicable to the unchanged runtime code. It is not a fresh runtime run on the documentation commit.
- The handoff-document commit also passed the Environment Validation and Engineering Execution OS Compliance workflows, as recorded in the current session report. Do not represent those as runtime test runs.
- Latest runtime CI run: `42479139321`, on exact HEAD `74463b279bbe87957c3431f0732db35ae1ee80f6`, completed SUCCESS. Registry validator passed (6 profiles, 25 agents, 13 adapters, 11 workflows, 10 native skills, 33 mirrored OpenHands skills); full unittest discovery ran **13 tests, all OK**. Job: `128727022927`. Run: https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42479139321

## Security correction completed after the initial handoff

- Finding: `build_plan()` previously trusted `task.owner_approval.approved_actions` from the task JSON envelope. Because task envelopes are untrusted input, this allowed the request itself to assert Owner consent.
- Correction: `scripts/blind_sniper_runtime.py` now initializes approved actions as empty during planning; task-envelope approval claims cannot satisfy consequential-action gates. Approval must be supplied at the guarded transition boundary by the host caller.
- Regression test: `test_task_envelope_cannot_self_approve_high_risk_action` proves a task that requests `merge` and self-asserts approval still has `merge` pending and cannot enter `EXECUTING` without a separate transition approval.
- Evidence: commits `93e5c089c6456b5cfafb97c9be1bb000926aeac1` and `74463b279bbe87957c3431f0732db35ae1ee80f6`; runtime CI run `42479139321` passed 13/13.
- Remaining limitation: transition-level approval is still a caller-supplied action list, not a cryptographically authenticated Owner receipt. Do not claim Owner identity/provenance is solved.

## OpenHands dispatch status — important distinction

- Issue #8, `[OpenHands] Complete existing Blind Sniper OS orchestration integration and E2E verification`, is open: https://github.com/madnessgate44-debug/Blind-sniper-/issues/8
- A live fetch of issue #8 returned **zero comments**. No dispatch receipt, OpenHands session ID, correlated result, PR or execution artifact is recorded on that issue. Therefore the requested OpenHands coding task is **NOT VERIFIED AS DISPATCHED OR STARTED**.
- PR #6's description separately reports one correlated, read-only OpenHands handoff (T013) through Brain issue #292, with a request comment, resolver session ID and result comments. That is evidence for that separate read-only handoff only; it does not prove issue #8 was dispatched, nor does it prove code execution or artifact return.

## Runtime capability truth

The engine remains a registry-aware planner and guarded task lifecycle state machine. It does not itself spawn agents, invoke tools, run browser sessions, or provide a durable shared cross-session task store. Approval flags are caller-supplied and are not cryptographically authenticated Owner receipts. Verification/review gates still accept simple evidence fields and need stronger task/commit/reviewer provenance. The browser, continuous background runner, and automatic transcript export remain unproven or blocked as described in the main handoff.

## Required Claude review focus

1. Review the exact current integration HEAD above, not the older PR #6/#7 heads.
2. Treat runtime CI run `42478361100` as passing evidence for parent `013ed5d...`, and distinguish it from checks on the documentation-only HEAD.
3. Explicitly state that issue #8 has no dispatch/result comments and that PR #6's T013 is a separate read-only Brain handoff.
4. Prioritize registry/runtime duplication, approval provenance, evidence binding, durable persistence/recovery, idempotent dispatch, and a real callable execution receipt before expanding browser scope.
5. Do not modify files, merge PRs, deploy, provision paid resources, or alter secrets/permissions as part of the review.

---

**Prepared:** 8 November 2026  
**Repository:** https://github.com/madnessgate44-debug/Blind-sniper-  
**Integration branch:** `feat/blind-sniper-orchestration-integration-2026-11-08`  
**Audience:** Claude — independent architecture reviewer and advisor  
**Owner:** Ahmed (Natural Intelligence / final authority)  
**AI operating lead:** Blind Sniper (ChatGPT in the current build phase)

> **Purpose of this document:** Give Claude the full project context, the design intent, the work completed in today's session, the known gaps and the decisions that still need expert challenge. Claude is being asked to advise and independently inspect—not to assume implementation authority, edit files, merge PRs, or declare the system complete.

---

## 1. Executive brief

Blind Sniper is intended to become a persistent, owner-governed AI operating environment—not merely a prompt pack, collection of Markdown instructions, agent directory, or thin wrapper around one model.

The target environment should let its AI operating lead:

1. Understand the Owner's intent and persistent project context.
2. Inspect the real workspace and source-of-truth artifacts.
3. Translate requests into bounded, evidence-backed task contracts.
4. Select the appropriate operating profile, skills, agents, tools and workflow.
5. Dispatch work to available execution agents where a real integration exists.
6. Supervise progress, preserve state, handle failures and recover safely.
7. Verify outputs against explicit acceptance criteria and source evidence.
8. Obtain Owner approval before consequential actions.
9. Close work with a durable receipt and update continuity state.
10. Improve its own operating environment through controlled, reviewable changes.

The system must distinguish **designed**, **documented**, **registered**, **available in this host**, **actually invoked**, and **verified end-to-end**. A Markdown file describing a capability is not proof that the capability runs. A registry entry is not proof of a live connector. A test of a planner is not proof that an agent was spawned.

The immediate build priority is to finish the **orchestration/control plane and its supporting operating files**. The independent browser engine is explicitly deferred until orchestration is coherent and verified.

## 2. Ownership, authority and working model

- **Ahmed = Owner / Natural Intelligence (NI).** Ahmed supplies direction, judgment, priorities and explicit approvals. He owns the final authority.
- **Blind Sniper = AI operating lead.** It is responsible for translating intent into specifications, managing its operating environment, using authorized tools, coordinating execution, verification and reporting.
- **Claude = independent reviewer/advisor for this handoff.** Claude should challenge architecture, identify gaps and propose improvements with evidence. Claude is not authorized by this handoff to change repository files or merge anything.
- **OpenHands = delegated coding executor when quota and integration permit.** OpenHands quota was believed exhausted during today's session, so the current work was carried out directly through the GitHub connector. That is a temporary execution constraint, not a reason to make OpenHands a mandatory dependency.
- **Forge = intended future browser/execution capability provider.** Do not assume Forge's browser MCP is connected to this ChatGPT host. It is currently treated as unregistered/unverified for authenticated browser interaction.
- **Shadow = provider-pool custodian in the wider Brain architecture.** Do not invent a separate “Ghost” role or attribute provider-key custody to the wrong agent. Provider credentials and key access must remain governed by actual authorized systems and never be copied into this repository.

The Owner primarily operates from an Android phone and expects the AI agents and connected tools to do the engineering work. Workflows should not depend on Ahmed having a laptop, local IDE, shell, or manual code-editing ability.

Cost policy: prefer free/zero-cost resources. Do not create paid resources, subscribe to services, provision paid infrastructure, change secrets/permissions, deploy production, merge, or perform destructive/irreversible actions without explicit Owner authorization.

Engineering lifecycle: **INSPECT → SPECIFY → PLAN → EXECUTE → VERIFY → CLOSE**. Root-cause analysis precedes patches. Inspect actual files and baseline state. Map requirements to files and evidence. Preserve passing behavior. Do not use placeholders or claim tests/actions that were not run.

## 3. What is being built: target architecture

The intended architecture has distinct layers. Claude should assess whether these boundaries are correct and sufficiently enforceable.

### A. Owner interface and session continuity
- Owner identity, authority, preferences, cost limits, risk tolerances and approval policy.
- Session boot and resume protocol.
- Persistent project map, active task list, decisions, checkpoints and evidence index.
- Task IDs and correlation IDs linking GitHub issues/PRs, agent runs, artifacts and reports.
- Session close/checkpoint procedure.
- Recovery protocol after interruption, quota exhaustion, partial execution or inconsistent state.

### B. Intent intake and task contract
Every task should be normalized into a contract containing at least:
- Stable task ID and objective.
- Context, source-of-truth links and repository/branch/commit.
- Scope, explicit non-goals and constraints.
- Acceptance criteria and verification plan.
- Risk classification and required Owner approvals.
- Required skills, agents, adapters and outputs.
- Dependencies, timeout/retry policy and loop breaker.
- Evidence and closure requirements.

The intake stage must ask only for essential missing information. It should not force unnecessary forms or silently invent requirements.

### C. Runtime registry / control plane
The registries should be the machine-readable source of truth for:
- Capabilities and adapters.
- Operating profiles.
- Agent roles and their contract locations.
- Skills and their metadata/paths.
- Workflows, triggers, steps, dependencies and required capabilities.
- Policies, permissions, cost boundaries and approval requirements.
- Templates and runtime entrypoints.

A validator must check both structural integrity and cross-registry references. More importantly, a runtime must consume the registries; they cannot remain decorative JSON.

### D. Skill selection and loading
- Skills need stable IDs, semantic descriptions, trigger conditions, tool requirements and explicit paths.
- Selection must be explainable and constrained by the active profile.
- The host must actually load/read the selected skill contract before relying on it.
- Skill composition and conflicts should be explicit.
- A skill should not claim tools or permissions that the active host does not have.

### E. Agent selection, contracts and delegation
- Agent roles should define purpose, allowed scope, forbidden actions, inputs, outputs, tool requirements, model/provider constraints, reporting format and escalation rules.
- Workflow selection should identify the roles required at each step.
- Delegation should use a bounded task envelope and a structured result/receipt.
- Agent spawn, message delivery and result retrieval must be represented as separate capabilities.
- If an agent cannot be invoked in the current host, the runtime must say so and fall back to a host-supported action—not pretend dispatch occurred.
- Independent review should be distinct from implementation, with evidence-based findings and severity.

### F. Workflow orchestration and state machine
- Workflows should have ordered steps, dependencies, state transitions, failure paths, retries and loop-breaking.
- The engine should know whether a step is pending, running, blocked, failed, verified or complete.
- High-risk transitions must be guarded.
- A workflow must not close just because all planned steps were attempted; it closes only when evidence and review gates pass.
- State and event history must persist and be recoverable.

### G. Tool and adapter boundary
- One registry should describe tools/adapters and their actual status in the current host.
- Tool status must distinguish available, partial/host-assisted, blocked, unverified and unavailable.
- Each workflow must declare the precise capabilities it needs, not merely a generic adapter name.
- The host must re-check live permissions/capability before invocation.
- MCP registration, authentication, tool discovery and invocation should be independently represented and verified.

### H. Policy, safety and governance
- Read-only by default where possible.
- Explicit Owner approval for merge, production deployment, secret mutation, permission changes, paid provisioning, destructive operations and other consequential actions.
- Approval must be action-specific, scoped and auditable—not a generic boolean that accidentally authorizes several unrelated actions.
- No credential/key material in repository files.
- No unsupported claims of background autonomy, persistent execution, browser access or agent dispatch.
- Preserve source licenses and provenance for imported assets.

### I. Evidence, observability and closure
- Evidence ledger with source refs, commit SHAs, CI runs, test results, timestamps and status.
- Verification against the exact candidate commit.
- Independent review report.
- Closure receipt with outcome, residual risks, deviations, artifacts and next action.
- Persistent checkpoint for future sessions.

### J. Browser (later phase; explicitly not now)
Blind Sniper should eventually have an independent browser capability, not merely assume it can borrow Forge or OpenHands' browser. The eventual design may require a durable host/runner, browser automation, authenticated session management, MCP exposure, allowlisted tools, audit logging, secure secret handling, persistence and recovery. **Do not build this during the current orchestration phase.** For now, document the requirement and keep browser workflows blocked until the actual integration is registered and verified.

---

## 4. Reverse-engineering reference: Claude Code Showcase

The primary reference selected for study is:

- **ChrisWiles/claude-code-showcase:** https://github.com/ChrisWiles/claude-code-showcase
- A fork encountered during research: https://github.com/mendelevium/claude-code-config

The objective is to reverse-engineer useful architecture and operating patterns—not blindly clone an implementation or assume Claude-specific hooks/configuration will execute in ChatGPT.

Files directly inspected during today's work included:
- `.claude/skills/README.md`
- `.claude/settings.md`
- `.claude/agents/code-reviewer.md`

Observed patterns:
- Skill catalog grouped by category, with metadata such as name, description, optional allowed tools and model.
- Skill descriptions and trigger rules used for semantic selection.
- Skill registration requires both a catalog entry and trigger/selection rules.
- Composable skills rather than one giant prompt.
- Agent contracts with clear role metadata and review checklists.
- Review severity categories (Critical, Warning, Suggestion), line-specific findings and checks for logic, style, immutability, error handling, UI states, tests, security and performance.
- Hook lifecycle concepts: prompt-submit skill evaluation, pre-tool guards and post-tool formatting/testing.
- Settings/configuration, MCP templates, permission templates, LSP integrations, CLI scripts, reusable commands and CI checks are part of a complete environment.

Important limitations:
- The attempted `.claude/commands/README.md` path returned 404; the actual command layout still needs to be established from the repository tree rather than guessed.
- Claude Code hooks, environment variables, MCP configuration and CLI scripts are runtime-specific. Blind Sniper must adapt their intent to capabilities actually available in its host.
- The `mendelevium/claude-code-config` fork was not copied verbatim because a usable license was not established. Compatible patterns were independently authored. Verify license status before any further source reuse.

Claude should identify any important showcase components or files that were missed and recommend a systematic source-to-target mapping.

## 5. Other source projects imported for study

PR #7 previously collected source-preserving assets and native adaptations from these projects:

1. **0xenzyme/agent-harness** — MIT. Intake/init/execute skills, worker-runner contracts and Codex-native execution notes.
2. **SUNRNEHUI/agent-harness** — MIT. Harness skill, task specification and subagent task templates.
3. **os-factory/har** — Apache-2.0. Factory-line and new-plugin skills.

These imports are reference material and licensed source assets. They are **not automatically executable plugins** merely because they exist in the repository. Their native adaptations need to be connected to real registries, selectors and runtime paths. Preserve license files and attribution. See `chatgpt-home/source-library/README.md` on the integration branch for the source index.

Native adaptation files transferred into the integration branch include:
- Agents: `harness-controller.md`, `worker-executor.md`, `independent-reviewer.md`, `factory-orchestrator.md`.
- Workflows: `idea-to-contract.md`, `isolated-execution-line.md`, `plugin-and-tool-onboarding.md`, `verification-and-handoff.md`.
- Skill: `github-research/SKILL.md`.

Claude should review whether these imported concepts are correctly adapted, whether any source content is redundant, and how to connect them without creating parallel/duplicate registries.

## 6. Repository and branch state at handoff

Repository: `madnessgate44-debug/Blind-sniper-`  
Default branch: `main`.

Two pre-existing PRs remain open and unmerged:
- **PR #6:** https://github.com/madnessgate44-debug/Blind-sniper-/pull/6  
  Feature branch: `feat/blind-sniper-codex-runtime-v3`  
  Runtime registry/control-plane baseline. At last check GitHub reported it open and mergeable.
- **PR #7:** https://github.com/madnessgate44-debug/Blind-sniper-/pull/7  
  Feature branch: `feat/blind-sniper-source-imports-2026-11-08`  
  Source imports and native adaptations. At last check GitHub reported it open and mergeable. Its base is PR #6's feature branch, not `main`.

Today's work was placed on a separate branch:
- **`feat/blind-sniper-orchestration-integration-2026-11-08`**
- It was created from PR #6's runtime head, then source-preserving files and native adaptations from PR #7 were copied onto it.
- This is a reconciliation/integration branch. It does not merge either original PR and does not authorize merging.
- The branch has been modified directly through the GitHub connector. The latest engine file blob observed at handoff was `ef597829bf93679b3745017e08d13e666337823f`; latest test file blob observed was `6d47b4b82204efc1bcc38a5f00378cc6a99c4aa3`. These are file/blob SHAs, not asserted branch HEAD SHAs.
- No PR has yet been opened for this integration branch.
- No merge to `main` has been performed.

The runtime baseline in PR #6 previously reported:
- 6 profiles, 26 agents, 11 adapters, 10 workflows, 10 native skills and 33 OpenHands library skills (as stated in its runtime documentation/CI receipt).
- Earlier CI receipts cited in the repository belong to a preceding checkpoint. They must not be treated as proof that today's new engine/tests passed.

### Key existing runtime files
- `chatgpt-home/runtime/capabilities.json`
- `chatgpt-home/runtime/profiles.json`
- `chatgpt-home/runtime/agents.json`
- `chatgpt-home/runtime/workflows.json`
- `chatgpt-home/runtime/skills.index.json`
- `scripts/validate_blind_sniper_runtime.py`
- `tests/test_blind_sniper_runtime.py`
- `.github/workflows/blind-sniper-runtime.yml`

The existing validator/tests were primarily structural at the point of inspection. They validated asset counts and registry consistency but did not prove the full task-routing and guarded orchestration path.

---

## 7. Work performed today (8 November 2026)

### A. Integration branch and source reconciliation
- Created `feat/blind-sniper-orchestration-integration-2026-11-08` from PR #6's runtime head.
- Copied the relevant source-preserving files and native adaptations from PR #7 onto this branch.
- Left PR #6 and PR #7 open and unmerged.
- No production deployment, paid provisioning, secret changes or permission changes were performed.

### B. Added an executable orchestration planner
New file:
- `scripts/blind_sniper_runtime.py`

Intended behavior:
1. Load the runtime JSON registries.
2. Route an incoming task to a registered workflow, or validate an explicit workflow selection.
3. Select a corresponding operating profile.
4. Select eligible agent roles from the profile and resolve their contract paths.
5. Select skills using deterministic keyword matching constrained by the profile, or validate explicit skill selections.
6. Resolve selected skill files and fail if a selected contract is missing.
7. Resolve workflow adapters and check their declared capabilities.
8. Compute readiness: READY, PARTIAL or BLOCKED.
9. Identify consequential requested actions and require action-specific approval.
10. Create a task state document and persist transition events.
11. Guard lifecycle transitions, requiring verification evidence before review and a PASS review verdict before closure.

The engine deliberately does **not** spawn agents, invoke tools, run browser sessions or claim that external work occurred. It is a planner and guarded lifecycle engine. Host integrations must perform actual dispatch/invocation and report receipts.

### C. Registered capability requirements in workflow registry
The workflow registry now carries explicit required capabilities for certain sensitive or currently unavailable workflows, including:
- Release gate: GitHub merge and Vercel deploy.
- OpenHands two-way handoff: session-result retrieval.
- Forge browser roundtrip: authenticated browser interaction.
- Continuous autonomy: background execution receiver and persistent runner.
- Conversation archive export: conversation export.

This was intended to stop a generic adapter label from being mistaken for the exact capability a workflow needs. The engine was then refactored to read capability requirements from `workflows.json`, keeping the registry as the source of truth.

**Claude should inspect this carefully:** confirm that the registry schema, capability names and status normalization are consistent with the existing adapter definitions, and that missing requirements fail closed.

### D. Added behavioral tests
New file:
- `tests/test_blind_sniper_orchestration.py`

Test scenarios currently authored:
- Engineering task routing to engineering profile/workflow.
- Research task routing to research profile/workflow.
- Unknown workflow rejection.
- Missing task correlation ID rejection.
- Browser workflow blocked when required adapter/capability is not available.
- High-risk action requires explicit action-specific Owner approval.
- Release workflow detects missing merge/deploy capabilities.
- Verification evidence required before review.
- Independent PASS review required before closure.
- Invalid lifecycle jumps rejected.

These tests have been committed to the integration branch, but **they have not yet been run in a local shell or confirmed passing in GitHub Actions at the time this handoff was written**. The CI workflow was updated to discover all `tests/test_*.py` tests and to include the new engine/test files in path filters. Check the actual Actions run before claiming success.

### E. Added runtime documentation and registry pointer
- `chatgpt-home/runtime/EXECUTION_ENGINE.md` documents the engine, commands, routing and limitations.
- `chatgpt-home/runtime/workflows.json` registers the engine entrypoint and workflow-level required capabilities.
- `chatgpt-home/runtime/README.md` and `chatgpt-home/README.md` were extended to index the runtime engine and imported source/adaptation material.

### F. What was not completed
- No end-to-end task was run through an actual spawned agent.
- No OpenHands session was dispatched/retrieved through a proven two-way API.
- No browser integration was built or tested.
- No autonomous background runner was proven.
- No MCP endpoint was newly registered or authenticated.
- No full Claude Showcase tree audit has been completed; only selected source files were directly inspected.
- No complete source-to-target reverse-engineering matrix has yet been committed.
- No CI run for the latest integration branch was verified at handoff.
- No PR was opened from the integration branch to `main`.
- No PRs were merged.

---

## 8. Important design risks and questions Claude must challenge

Please do not simply endorse the design. Inspect the actual branch files and identify flaws.

### 8.1 Registry schema and runtime authority
- Are the JSON registries normalized and sufficiently expressive?
- Are there duplicate sources of truth between registry metadata, agent/skill Markdown contracts, workflow Markdown and the Python engine?
- Should routing maps currently hardcoded in Python (workflow-to-profile, workflow-to-agent, keyword skill map) move into the registries?
- What schema/versioning and migration strategy is needed?
- How should the runtime validate references, contracts, permissions and adapter capability claims?

### 8.2 Task routing quality
- Is deterministic keyword matching an acceptable first stage, or should the host model produce a structured selection proposal constrained by a deterministic policy validator?
- How should confidence, ambiguity, skill conflicts, profile compatibility and fallbacks work?
- How do we prevent an overly broad keyword from selecting a dangerous workflow or the wrong agent?
- What should happen when no suitable skill or agent exists?

### 8.3 Agent contracts and execution
- Are agent role IDs and contract paths actually consistent with the registries?
- Are role names such as planner, engineer, QA verifier, reviewer, Shadow auditor, release manager, Watcher and recovery agent grounded in existing registered agents?
- Are contracts bounded enough to prevent role overlap and uncontrolled tool use?
- What structured envelope/result/receipt protocol should be standardized?
- How should retries, cancellation, timeouts, partial results and duplicate dispatch be handled?
- How do we model agent spawn, message send, session retrieval and artifact verification as distinct capabilities?

### 8.4 Lifecycle and state persistence
- Is the current state machine complete and safe?
- Are terminal states, retries, rollback, pause/resume and recovery represented correctly?
- Is append-only JSON event persistence adequate, or should a durable task store be used?
- Can a state file be corrupted or silently overwritten?
- Should transitions be validated against workflow-specific graphs rather than one global graph?
- How do we ensure evidence is bound to the exact task and commit, not merely a boolean such as `verification_passed: true`?

### 8.5 Approval model
- The current engine accepts exact action strings as approval inputs, but the trust boundary is the host caller. How should Owner identity and approval provenance be authenticated?
- Is an approval receipt needed with task ID, action, scope, expiry, approving Owner, and confirmation source?
- Can a single approval be replayed or accidentally reused?
- Are all consequential actions enumerated and classified?
- Ensure the system never treats an AI-generated field as Owner authorization.

### 8.6 Capability truth and host adaptation
- The current status normalizer is intentionally simple. Is it robust enough?
- How should per-tool permissions, authentication state, rate limits, availability and session-scoped capabilities be modeled?
- How can the engine prevent stale registry snapshots from being mistaken for current host capability?
- How should unavailable tools be replaced with a safe host-native route?
- How do we represent tools that are technically available but not authorized for the current task?

### 8.7 Hooks, commands and skills
- Which Claude Showcase hook concepts map to ChatGPT host behavior, and which cannot be implemented in this runtime?
- Should hooks be modeled as policy checkpoints in the host orchestration rather than copied shell scripts?
- What is the best design for a discoverable command catalog?
- What is the minimal metadata schema for skills, and how should skill loading be proven?
- Which parts of the imported harnesses are useful and which add unnecessary complexity?

### 8.8 Test strategy
- The current behavioral tests are only a start. What unit, contract, property-based, integration and failure-injection tests are required?
- How can CI validate that every workflow's adapters and required capabilities exist?
- How can tests prove no blocked workflow can execute?
- How can we test state recovery, concurrent updates, idempotency and loop breakers?
- What end-to-end test is meaningful without pretending that unavailable external agents or browser integrations exist?

### 8.9 Security and supply chain
- Review the license and provenance of every imported source file.
- Check for accidental secrets, prompt injection, unsafe shell commands or hidden network calls.
- Ensure imported agent instructions are treated as untrusted source content until reviewed.
- Review path handling and JSON parsing for malformed or malicious task input.
- Check that approval flags/arguments cannot be supplied by an untrusted task file and treated as Owner consent.

### 8.10 Scope and sequencing
- Is the correct order: registry/schema normalization → execution contracts → orchestration engine → persistent state → host adapters → end-to-end tests → browser?
- What should be deferred or removed?
- What is the smallest architecture that can deliver reliable, useful orchestration without creating a large framework that only documents itself?

---

## 9. Required advice format from Claude

Please return an independent review with:

1. **Executive verdict:** sound direction / sound with major changes / not sound.
2. **Evidence examined:** exact branch, commit, paths and line references inspected.
3. **Critical findings:** bugs, unsafe assumptions, missing capabilities or architectural contradictions. Rank Critical / High / Medium / Low.
4. **Registry audit:** schema issues, duplicated sources of truth and missing cross-links.
5. **Runtime audit:** task routing, capability gates, approval model, state machine and persistence.
6. **Source-import audit:** license/provenance and whether adaptations are faithful and useful.
7. **Test audit:** tests that are missing, invalid or falsely reassuring.
8. **Recommended target architecture:** concrete file-level changes and dependency order.
9. **Minimal next implementation sequence:** numbered, testable tasks with acceptance criteria.
10. **Explicit non-goals:** confirm that the independent browser is deferred and that unavailable integrations must not be represented as live.

For each finding, provide:
- Evidence (path + line/section or registry key).
- Why it matters.
- Severity.
- Recommended correction.
- How to verify the correction.

Do not modify files or merge branches as part of the review. Send the findings to Ahmed and Blind Sniper so the Owner can decide the next implementation steps.

---

## 10. Immediate next steps for Blind Sniper after receiving Claude's review

1. Re-fetch the integration branch and inspect its exact current HEAD; do not rely on this handoff's blob SHAs as branch HEAD.
2. Run the existing runtime validator and the full Python test suite on the integration branch through GitHub Actions or another actually available runner.
3. Fix all Critical/High issues before expanding scope.
4. Complete the Claude Showcase repository tree audit and commit a source-to-target matrix with evidence and license notes.
5. Normalize registries and remove duplicated hardcoded routing logic where justified.
6. Complete agent/skill/workflow contracts and prove that runtime selection resolves real files.
7. Implement reliable task persistence, event integrity, resume/recovery, idempotency and loop breakers.
8. Add host adapter dispatch only where an actual tool exists and can return a verifiable receipt.
9. Perform end-to-end tests for the integrations that are truly callable.
10. Keep the browser engine deferred until the orchestration/control plane passes its acceptance criteria.
11. Present a reviewable PR to the Owner. Do not merge without explicit approval.

## 11. Definition of done for the current orchestration phase

The current phase is complete only when Blind Sniper can, using its own checked-in operating files and real host capabilities:

- Boot and resume from persistent state.
- Accept an Owner task and produce a complete task contract.
- Inspect actual repository/source state.
- Select the right profile, skills, agents and workflow from registries.
- Verify all selected contracts and required capabilities.
- Dispatch to a real execution path or explicitly report a block.
- Enforce scope, cost, permissions and Owner approvals.
- Persist state and evidence across interruptions.
- Recover safely from partial failure.
- Verify outputs against acceptance criteria and exact commit.
- Obtain an independent review.
- Produce an accurate closure receipt.
- Pass automated tests covering success, rejection, blocked capability, recovery and failure paths.

A planner that only emits JSON is a useful intermediate milestone, **not the completed operating system**.

---

**Final instruction to Claude:** Treat this as a serious architecture review of an evolving AI operating environment. Challenge assumptions, inspect actual files and report evidence. Do not confuse design intent with implementation reality. The goal is a dependable, owner-governed operating system—not an impressive-looking directory tree.


---

# Current implementation addendum — native Codex core and task ledger

**Updated:** 8 November 2026  
**Branch:** `feat/blind-sniper-orchestration-integration-2026-11-08`

This addendum supersedes earlier role/authority descriptions where they conflict with the current architecture.

## Operating boundary

- Blind Sniper is self-contained first: native planner, researcher, engineer, reviewer, QA, security and recovery contracts are the core workforce.
- OpenHands and Forge are optional future adapters. No external agent or external coordination repository is required for core task intake, planning, execution, memory, recovery or verification.
- Do not introduce a Ghost role. Do not depend on Shadow or Watcher.
- Ahmed provides direction and human-only decisions. Blind Sniper owns routine technical decisions and bounded engineering execution; no routine code edit, test, documentation change or engineering choice is routed to Ahmed for approval.

## Changes committed in this window

| Commit | Change |
|---|---|
| `85243d273ddde9fa0c6eb6c431a96551a103ed87` | Added native append-only hash-chained JSONL task ledger |
| `e8384870d78ae4bc4935fcd2b37bf00b9a640468` | Added five ledger tests |
| `32f38a7cf1e1be8a590fcc14fe52c76aa48fc016` | Added ledger module and tests to runtime CI path filters |
| `d2326a14ca772cb96f0846208be169e8bf30c52d` | Routed review/recovery through native role contracts |
| `0393a2b14e15df0e5cbe301d4b00585e26660fa6` | Documented ledger semantics and limits |
| `869d6bc2fd688a8360f0fb10e1cfa4b8153f2a66` | Rewrote architecture authority boundary: native core, external adapters optional |
| `fb2005b23161fe0b61b248fe138e2ac4f0e7e289` | Updated runtime README to remove external provider-custodian dependency |

## Verification

- [VERIFIED] Runtime registry validator passed on `fb2005b23161fe0b61b248fe138e2ac4f0e7e289`.
- [VERIFIED] GitHub Actions runtime run `42480781716` succeeded on exact SHA `fb2005b23161fe0b61b248fe138e2ac4f0e7e289`.
- [VERIFIED] Full Python discovery ran 18 tests, all passed. This includes all five new ledger tests: restart/replay, idempotency, idempotency-key conflict, tamper detection and unknown task handling.
- [VERIFIED] Runtime registry validation passed: 6 profiles, 25 agents, 13 adapters, 11 workflows, 10 native skills, 33 mirrored OpenHands skills.
- [VERIFIED] Engineering Execution OS compliance and environment validation were also triggered on the updated architecture commit; see run IDs `42480778796` and `42480778739` (check final conclusions before relying on them).

## Honest remaining limits

- The ledger is durable only while its workspace/file survives. It does not yet synchronize state across ephemeral GitHub Actions runners or concurrent remote workspaces.
- There is no GitHub-backed compare-and-swap event store, no lease/claim queue, no stale-run recovery scheduler, and no full task submission→execution→resume E2E yet.
- The current runtime still plans and validates lifecycle state; it does not execute arbitrary shell commands or spawn native subagents. Role contracts are not separate running processes.
- PRs #3, #6 and #7 remain separate historical review artifacts; no merge to `main` occurred in this work window.

## Next implementation sequence

1. Add a GitHub-backed append-only task ledger with optimistic concurrency and immutable event commits.
2. Connect the planner/lifecycle CLI to the ledger and expose create, append, inspect and resume commands.
3. Implement a bounded native executor interface using only actual host tools/CI runners.
4. Add task claims/leases, idempotent step execution, cancellation and stale-lease recovery.
5. Bind verification receipts to task ID, exact commit SHA, workflow run ID and reviewer identity.
6. Add a restart/recovery end-to-end test against the GitHub-backed ledger.
7. Reconcile the full integration branch and open one consolidated PR to `main` after the runtime and privacy boundaries are sound.
