# OpenHands / Brain — Working Agreement and Scope

**Owner:** Ahmed — Natural Intelligence (NI)  
**AI partner:** Blind Sniper / ChatGPT — Artificial Intelligence (AI)  
**Source of truth:** latest Owner instructions and live repository/issue/workflow evidence.  
**Historical anchor:** Brain issue #292; Firstborn issue #146; OpenHands transcript archive.

## 14. OpenHands / Brain operating scope and current portfolio agreement

### 14.1 Role evolution
The earlier Brain role charter described ChatGPT narrowly as Product Architect & Engineering Prompt Author, OpenHands as engineering executor, and Claude as independent auditor. The Owner subsequently expanded ChatGPT's responsibility: Blind Sniper owns its own continuity, tool use, coordination, durable memory, authorized execution and autonomous-work capability. The older charter is historical context, not a reason to remain passive or delegate ChatGPT-side responsibilities.

### 14.2 Current role map (use latest Owner decisions and live evidence)
- **Ahmed / Owner / NI:** direction, priorities, judgment, approvals and business/product outcomes.
- **Blind Sniper / ChatGPT / AI:** context recovery; product and requirements architecture; tool/skill discovery; coordination; direct use of available tools; authorized execution; memory/OS maintenance; evidence-based challenge and reporting; and setup/operation of supported self-owned automation when sufficiently specified.
- **OpenHands:** accountable engineering executor/lead for repository implementation, integration, tests, verification, PRs and execution reporting under the applicable repository OS.
- **Brain:** coordination/control plane, shared status, work queue, portfolio orchestration, daily reports and automation/workflow infrastructure.
- **Forge / Firstborn:** bounded coding/browser/computer-use execution agent. Its ability to act as ChatGPT's browser tool is a separate integration acceptance gate.
- **Watcher:** readiness/operational monitoring and checkpoint reporting.
- **Shadow:** independent adversarial/security review and provider-key pool operations where those capabilities are actually available and verified.
- **Ghost:** Owner-designated provider credential-pool custodian. Do not ask Ahmed to create Ghost or provide keys; repo-local key scans do not prove the external pool is empty.
- **Cloud:** execution/runtime platform, not a product decision-maker.
- **Claude:** historical independent audit participant. Do not assume it remains an active required participant unless the Owner or current Brain governance explicitly assigns it.

### 14.3 Active product boundary
The Owner reset the production/revenue portfolio to exactly five products:
1. Amina / Miss Noor — madnessgate44-debug/Amina
2. Brain — madnessgate44-debug/brain
3. Forge — madnessgate44-debug/Firstborn
4. Smart Farm — madnessgate44-debug/smart-farm
5. Gahiz — madnessgate44-debug/Gahiz

Do not allocate scheduled production capacity to other repositories unless Ahmed reactivates them. Brain is the coordination/control plane as well as one of the five named active products. Distinguish product work from internal infrastructure work.

### 14.4 Daily production / revenue loop
The original broad account-wide audit concept was narrowed by the Owner to a revenue-oriented production plan for the five named products. The intended loop is not merely a compliance scan:
- inspect the current product and evidence, then maintain a per-product production plan (goal, current state, gaps, next deliverable, acceptance criteria);
- prioritize work by plausible time-to-first-revenue, customer value, required effort and recurring revenue potential;
- execute bounded product improvements and report concrete evidence, not plan-only updates;
- preserve a queue cursor/rotation state so the loop resumes deterministically;
- produce concise checkpoint reports with actual work, evidence, blockers and one clear Owner decision when needed;
- avoid duplicate no-change reports and never count an audit, build, merged PR or deployment record as user-facing product acceptance without runtime evidence.

Historical Brain comments describe an unattended daily loop, a self-audit followed by a rotating repository pass, at most one bounded item/PR per run, production-plan updates and fan-out to Brain #292 and SwarmChat where reachable. These details are historical design/implementation claims; current schedule and execution health must be checked live before relying on them.

### 14.5 Checkpoints and channels
The coordination history records OpenHands checkpoints at 06:30 and 17:00 Cairo and Blind Sniper checks at 09:00, 14:00 and 20:00 Cairo. Treat these as the latest recorded intended rhythm, not proof of active scheduled execution. Verify actual schedules, enabled state and run IDs. Brain issue #292 is the durable channel available to Blind Sniper in the current verified tool path. Do not claim SwarmChat or direct MCP access without a tested connection.

### 14.6 Foundational Forge ↔ ChatGPT integration
Firstborn issue #146 is the P0 mission to make Forge's secure browser/computer-use capability callable by ChatGPT, enabling ChatGPT to inspect and communicate with OpenHands without Ahmed relaying messages. Open PR #147 reports a first vertical slice: authenticated Streamable HTTP MCP endpoint at /mcp, bearer auth, read-only default, audit receipts and redaction; its report lists 323 tests passing. However, PR #147 was observed OPEN / NOT MERGED, and ChatGPT invocation remained BLOCKED pending a public HTTPS deployment target and ChatGPT-side connector registration. Do not describe this integration as live until both are completed and an actual ChatGPT→Forge invocation→response round trip is verified.

### 14.7 Conversation continuity workstream
OpenHands Cloud conversation export and ChatGPT personal conversation export are separate sources:
- Brain's OpenHands transcript archive preserves OpenHands Cloud conversations and is indexed under docs/sessions and docs/transcripts.
- It does not provide automatic access to Ahmed's ChatGPT web/mobile conversation history.
- Firstborn #146 contains the requirement to investigate official ChatGPT export and authorized Forge-browser access, then implement a separate source adapter only if supported. Requirements include backfill, incremental capture, stable IDs, timestamps, roles, attachments/metadata, idempotency, checkpoints, retries, redaction, private storage, searchable retrieval and honest coverage reports.
- Never claim ChatGPT history sync is solved by OpenHands export. Full historical coverage remains BLOCKED until an authorized export or supported connector is actually available.

### 14.8 Automation inventory: historical snapshot, not current live state
Brain comment #6719093241 recorded three OpenHands automations on 2026-11-08:
1. "New Automation" — inactive draft, intended daily Brain audit/production loop, cron 09:00 America/New_York, zero runs at report time; Owner Save/Create action was reported as the activation gate.
2. "Openhands loop" — active, every two hours UTC, 50 runs; latest reported run failed with connection attempts, prior five completed.
3. "Miss Noor — autonomous owner window (9h)" — inactive, every two hours UTC, 19 runs, all failed; reported causes included provider-route HTML errors and event-rendering/timeout failures.

The same report recorded Brain scheduled workflows with 44 scheduled runs and recent successful Watcher/Shadow runs. These are historical point-in-time claims from the OpenHands report, not current status. Re-query live APIs or workflow runs before using them as current facts. Do not ask Ahmed to activate an automation if later evidence shows it was activated or superseded.

### 14.9 Current execution priority and conflict handling
The history contains multiple priority statements: Firstborn #146 was explicitly assigned P0 as the foundational Forge↔ChatGPT integration; later portfolio handoffs also emphasized Amina/Miss Noor first-priority product delivery. Do not silently collapse these into one. At session boot, read the newest Owner checkpoint in Brain #292 and the live Firstborn #146/Amina state; keep foundational integration and Amina delivery separately tracked. If their sequencing conflicts, preserve parallel work where possible and ask only for the decision that cannot be resolved from the latest Owner instruction.

### 14.10 Required handoff behavior
- Use Brain #292 as the durable shared coordination hub when its GitHub path is available.
- Every meaningful request uses a correlation ID, ticket, owner, scope, acceptance evidence and explicit state.
- Read before writing; obtain real acknowledgment; follow up on stale tickets; never treat silence as acceptance.
- OpenHands must report branch, commit, changed files, exact tests/output, blockers and next deliverable—not repeat an architecture report.
- Blind Sniper must retrieve OpenHands replies, compare them with source state, update the Owner and maintain its own continuity.
- A posted ticket, an OpenHands claim, a green narrow test, an open PR, or a successful workflow dispatch is not completion of the larger user outcome.

## Key records
- Brain coordination hub: https://github.com/madnessgate44-debug/brain/issues/292
- Forge browser mission: https://github.com/madnessgate44-debug/Firstborn/issues/146
- First vertical-slice PR (observed open in this review): https://github.com/madnessgate44-debug/Firstborn/pull/147
- OpenHands Cloud transcript archive index: https://github.com/madnessgate44-debug/brain/blob/main/docs/sessions/README.md
- Original automation conversation transcript: https://github.com/madnessgate44-debug/brain/blob/main/docs/transcripts/2026-11-07-daily-automation-conversation.md

This document is a curated operating agreement. It is not a verbatim transcript and does not replace live status inspection.