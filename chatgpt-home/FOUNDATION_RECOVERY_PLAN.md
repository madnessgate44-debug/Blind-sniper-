# Blind Sniper — Foundational Recovery and Agent Operations Plan

**Owner:** Ahmed / Natural Intelligence (NI)  
**Operator:** Blind Sniper / ChatGPT (AI)  
**Priority:** P0 — highest operating-system priority  
**Coordination hub:** https://github.com/madnessgate44-debug/brain/issues/292  
**Status:** ACTIVE PLAN; execution evidence is tracked per phase below.  
**Last reconciled:** 2026-11-08

## 1. Mission and ownership

Ahmed owns intent, priorities, judgment, approvals and outcome selection. Blind Sniper owns the AI-side system: its own OS, context recovery, research, tool discovery, agent coordination, authorized execution, verification, memory and reporting. Blind Sniper must not make Ahmed operate the machinery or relay messages when a verified direct path exists.

The operating system is the number-one priority because it enables every other project. This is not a documentation-only goal: a written capability is not considered operational until its trigger, permissions, execution path, output and failure handling are tested.

## 2. Non-negotiable architecture

Blind Sniper consists of five connected layers:

1. **Identity and policy:** canonical BLIND_SNIPER.md, root Engineering Execution OS, authority and approval boundaries.
2. **Memory and archives:** curated continuity + raw OpenHands Cloud archive + separate ChatGPT conversation archive + searchable index + checkpoints.
3. **Tools:** GitHub, web/research, Forge browser/computer-use, connected plugins and supported cloud execution. Only currently exposed and tested capabilities count.
4. **Agent network:** Brain as shared control plane; OpenHands as engineering lead; Forge as bounded executor/browser; Watcher as observer/analyst/service desk; Shadow as independent adversarial reviewer; Ghost as provider-pool custodian.
5. **Autonomy and reporting:** actual scheduled triggers, bounded tasks, durable tickets, run evidence, health checks, escalation and Owner reports.

A repository is persistent storage, not an always-on agent. A ticket is not an acknowledgment. A configured endpoint is not a connected tool. A transcript index is not proof that all raw events are recoverable.

## 3. Priority sequence

### P0-A — Complete and operationalize Blind Sniper OS

**Goal:** make the OS a usable runtime contract, not merely a collection of Markdown files.

Acceptance:
- Canonical OS and linked protocols agree on authority, roles, tool access, archive boundaries, ticketing, approvals, autonomy and reporting.
- Boot procedure retrieves the actual controlling files and current memory, records exact refs/SHAs, and reports COMPLETE/PARTIAL honestly.
- Capability registry lists each tool/agent, real channel, permissions, last successful end-to-end test, known limitations and owner.
- Every applicable interaction uses Brain #292 read-first/ticket/act protocol; newest comment ID and transcript delta are recorded.
- Session closeout updates continuity and checkpoint; write is re-fetched and verified.
- No stale role descriptions or undocumented agent assumptions remain in the canonical OS.

### P0-B — Recover and validate the full OpenHands Cloud archive

**Known starting point:** Brain docs/sessions/README.md currently reports 19 days, 142 conversations and 577 Owner messages (2026-10-11 through 2026-11-03). It says raw gzip events are under .openhands/export/raw/ and gitignored. The readable day logs and selected transcript are useful, but do not by themselves prove raw archive completeness or current coverage.

Execution:
1. Locate the authoritative OpenHands Cloud export source, exporter, raw store, manifests and checkpoints. Inspect the actual filesystem/workflow/automation that owns them.
2. Determine whether the gitignored raw archive exists, is backed up, and can be retrieved by Blind Sniper; never infer availability from a README.
3. Reconcile source conversation IDs and event counts against day logs, transcripts and index; enumerate missing dates, sessions, event types and attachments.
4. Backfill missing accessible sessions; preserve raw source immutably and redact secrets in derived/searchable outputs.
5. Make export incremental and idempotent, with checkpoints, retry/resume, duplicate detection, checksums, parse-error quarantine and coverage report.
6. Ensure Blind Sniper can search by date, project, participant, conversation title, phrase and decision, then open the source transcript with provenance.

Acceptance:
- Source inventory and coverage matrix exist.
- Every source item is accounted for as archived, intentionally excluded with reason, inaccessible, or parse-failed.
- Counts reconcile; no claim of complete while any source remains unexplained.
- A historical decision is retrieved from the archive by Blind Sniper and its original transcript is linked.
- A harmless new OpenHands conversation is captured incrementally and retrieved without duplication.

### P0-C — Recover Blind Sniper's own ChatGPT ↔ Ahmed archive

This is a separate source from OpenHands Cloud. Do not use the OpenHands exporter as evidence of ChatGPT history capture.

Execution:
1. Inspect official ChatGPT data-export options and the user's authorized export files/connectors.
2. Determine which prior ChatGPT conversations are accessible through supported mechanisms. Backfill only from an authorized source.
3. Determine whether ongoing incremental capture of future conversations is supported through a documented, authorized interface. No undocumented/private endpoint, session scraping, or access-control bypass.
4. If ongoing capture is unsupported, establish the best supported user-authorized export/import workflow and report the exact limitation; do not claim automatic capture.
5. Preserve roles, timestamps, conversation/message IDs, order, text, available tool events and attachment metadata; maintain private storage, secret redaction, checksums, deduplication, checkpoints, retries and searchable index.
6. Prove retrieval of a prior Owner decision in a later session and capture/retrieve a harmless new test conversation if a supported ongoing route exists.

Acceptance:
- Explicit source-by-source coverage report (complete/partial/unavailable).
- No conflation of curated summaries, OpenHands logs and raw ChatGPT transcripts.
- Blind Sniper can retrieve a prior decision with provenance.
- Incremental capture is declared VERIFIED only after a real test conversation is automatically archived and retrieved.

### P0-D — Close Forge as Blind Sniper's browser/computer-use tool

Forge is not merely another coding agent. It is intended to be Blind Sniper's browser and computer-use interface for research, inspection, interaction and communication with external agent surfaces, including OpenHands.

Known state at last inspected report:
- Firstborn issue #146 defines FORGE-CHATGPT-BROWSER-001.
- PR #147 adds authenticated Streamable HTTP MCP /mcp, bearer auth, read-only default, redaction and browser audit receipts; OpenHands reported 323 tests passing.
- PR #147 was observed OPEN / NOT MERGED.
- Public HTTPS deployment and ChatGPT connector registration were still blockers. A local endpoint or passing MCP test is not ChatGPT integration.

Execution:
1. Re-read Firstborn governing files and issue #146; inspect PR #147, current branch, CI and runtime.
2. Resolve a persistent browser-capable host compatible with long-lived Chromium. Compare available zero-cost/no-card options first; no paid host or spend without Ahmed's approval.
3. Deploy authenticated endpoint with TLS, secret-safe configuration, health/readiness, durable logs and explicit read-only/consequential-action policy.
4. Register the connector through the supported ChatGPT connector mechanism when the platform permits it.
5. Perform a real ChatGPT-initiated round trip: Blind Sniper opens an authorized harmless page, reads/extracts information, performs a permitted interaction only when authorized, reads browser history/audit receipt, and closes session.
6. Test unauthorized access, missing/wrong token, read-only denial, redaction, session cleanup and outage recovery.
7. Use Forge to access the authorized OpenHands task surface, send a correlated message, retrieve its actual reply, inspect resulting artifacts and send a follow-up.

Acceptance:
- PR merged under repository policy; deployment healthy.
- ChatGPT connector registered and available in the actual tool inventory.
- A real ChatGPT→Forge→browser→result round trip passes.
- A real Blind Sniper↔OpenHands communication round trip passes without Ahmed relaying.
- Audit trail, auth, read-only gate and secret handling pass.

## 4. Agent capability and responsibility registry

| Agent/system | Intended responsibility | Evidence / current boundary | Blind Sniper interaction |
|---|---|---|---|
| Ahmed / NI | Owner, priorities, judgment, approvals | Current Owner instruction | Ask only for real decisions/approval |
| Blind Sniper / ChatGPT | AI operating lead for own OS, research, memory, tools, coordination and reporting | Current session tools are authoritative; no persistent runtime between turns unless an external trigger exists | Owns this OS and #292 |
| OpenHands | Accountable engineering executor for repository implementation, integration, tests and PRs | OpenHands Cloud archive and Brain reports exist; live execution must be checked per task | #292 now; Forge direct channel target |
| Brain | Orchestration/control plane, work queue, shared status, scheduled workflows and archives | Brain repo, #292, ticket protocol and Actions; workflow health must be checked live | GitHub issue #292 |
| Forge / Firstborn | Browser/computer-use and bounded coding executor | PR #147 is partial HTTP MCP implementation; ChatGPT access unproven | Target: authenticated MCP connector |
| Watcher | Observer, researcher, trend/problem analyst and service desk; reads repos, issues, PRs, chats, logs and knowledge; identifies recurring symptoms/root causes; proposes bounded improvements; reports evidence | WATCHER.md v1.1 defines this role. watcher/connectors.md is dated 2026-11-01; ChatGPT/Forge channel was only PARTIAL and autonomous receiver disabled in that snapshot | Immediate request posted in Brain #292 T004; wait for real reply; verify connector registry and receiver |
| Shadow | Independent adversarial/security reviewer; challenges Watcher and implementation evidence; provider/key pool operations only within verified permissions | WATCHER.md and shadow/registry.md; registry last updated 2026-11-01; Shadow workflow previously reported BLOCKED due to missing Gemini route/secrets, while Actions-secrets API permission was reported unavailable | Request independent review via Brain workflows; do not assume live model/credential access |
| Ghost | Owner-designated custodian of external Gemini/provider credential pool; maintains tested availability and supplies authorized routes to agents | Role is Owner-designated; actual runtime/API/channel and current key inventory must be proven. Never ask Ahmed to paste secrets or infer pool emptiness from repo-local secrets | Use only a verified Ghost channel/registry; request labels/status, never secret values |

**Role guard:** profiles and constitutions describe intended jobs; they do not prove a worker ran. Record runtime identity, trigger, permissions, artifacts, run ID and output before declaring capability VERIFIED.

## 5. Watcher operating loop — turn observation into useful action

Watcher should be Blind Sniper's sensor and analyst, not a passive report generator.

Required inputs (only where its connectors actually work):
- Brain #292, SwarmChat channels and ticket/transcript deltas.
- OpenHands conversations, task runs, failures and archive coverage.
- GitHub activity across the five active products: commits, PRs, issues, CI, workflow runs and releases.
- Forge sessions, browser receipts and integration failures.
- Shadow reports, security findings and provider/connector health.
- Relevant external research, reverse-engineering targets and learning material.

Required processing:
1. Ingest new events incrementally; preserve source links, IDs, timestamps and provenance.
2. Cluster repeated symptoms across agents/repos; distinguish correlation from root cause.
3. For each problem report: symptom → root cause → evidence → impact → smallest proposed fix → target owner → acceptance test.
4. Detect stale tickets, silent agents, blocked automations, unverified claims, repeated failed runs, scope drift and missing user-facing delivery.
5. Search external sources only when they can answer a concrete open problem; turn useful material into a lesson and bounded proposal.
6. Shadow challenges the evidence and proposed fix. Rejections include the root cause and corrective action.
7. Blind Sniper consumes Watcher's digest, prioritizes it against Ahmed's direction, routes work to OpenHands/Forge, and tracks result to verified closure.
8. Report to Ahmed with a short actionable digest: what changed, top problems, proposed actions, evidence links, what needs approval.

**Watcher handshake:** T004 was posted to Brain #292 asking for its latest real digest, exact sources/channels read, top recurring problems and verified direct ChatGPT/Forge communication path. Until Watcher replies, this is REQUESTED, not acknowledged. If the old autonomous receiver remains disabled, Brain #292 is the fallback; do not claim real-time monitoring.

## 6. Communication architecture and fallback

Primary durable room: Brain issue #292. For every applicable interaction:
1. Read newest comments and name the newest comment ID.
2. Post a ticket with agreement, ack, trace/transcript delta, one ask, finding, request and state.
3. Perform the work.
4. Read replies and artifacts; acknowledge and close the loop with evidence.

Secondary channels are not considered available until a successful test proves send AND receive:
- SwarmChat: verify server, channel membership, send, receive and timestamp.
- Forge MCP: verify public HTTPS, ChatGPT connector registration, auth and actual round trip.
- OpenHands Cloud: verify API/session access, task dispatch, response retrieval and artifact inspection.
- Watcher/Shadow workflows: verify trigger, latest run, logs, output artifact and audit result.

Fallback if a channel fails: post to #292, label the direct channel BLOCKED, include correlation ID, and continue only work that can safely progress. Never make Ahmed relay routine messages.

## 7. Reporting and cadence

The operating plan calls for three classes of report:
- **Session report:** at every substantive session closeout — current phase, evidence changed, blockers, next action.
- **Watch/coordination digest:** Watcher proposes daily findings; Shadow audits them; Blind Sniper synthesizes only after reading actual output.
- **Foundation checkpoint:** at least daily while P0 recovery is active, with phase gates and measurable coverage/integration status.

Historical Brain records mention 09:00, 14:00 and 20:00 Cairo Blind Sniper checks and 06:30/17:00 OpenHands checkpoints. These are intended historical rhythms, not proof of active automation. Verify schedules, timezone, enabled state and run IDs before relying on them. If no supported recurring trigger is active, state that clearly and use the next available session; do not promise unattended work.

Every report must distinguish:
- DESIGNED / CONFIGURED / RUNNING / EXECUTED / VERIFIED;
- REQUESTED / SENT / RECEIVED / ACKNOWLEDGED;
- archive indexed / raw available / reconciled / complete;
- MCP endpoint built / deployed / connector registered / end-to-end usable.

## 8. Current evidence ledger (initial)

| Workstream | State | Evidence | Next gate |
|---|---|---|---|
| Blind Sniper OS v2.0 | STARTED; PR #3 open | Branch files read; PR #3 open/unmerged | Add this plan, reconcile files, verify all changed docs |
| OpenHands archive | PARTIAL | docs/sessions/README.md: 19 days, 142 convos, 577 Owner msgs; raw gzip described as gitignored | Locate raw store/source and reconcile |
| ChatGPT archive | BLOCKED/UNKNOWN | Firstborn #146 requirement; no supported live source adapter verified | Official export/access feasibility and authorized source inventory |
| Forge integration | PARTIAL/BLOCKED | Firstborn #146, PR #147; HTTP MCP slice reported, ChatGPT access not proven | Deploy + register + real round trip |
| Watcher communication | REQUESTED | T004 comment posted in Brain #292 | Watcher response and send/receive test |
| Shadow capability | DEGRADED/UNKNOWN | Registry dated 2026-11-01; prior Shadow workflow blocked report | Fresh workflow/model/permissions test |
| Ghost capability | UNKNOWN | Owner-designated role, no current direct channel verified | Identify authorized interface and current pool health without exposing values |

## 9. Completion definition

The Blind Sniper OS foundation is not COMPLETE until:
- canonical OS and protocols are reconciled and adopted;
- both conversation archives have explicit, evidence-backed coverage reports and Blind Sniper can retrieve historical decisions from each accessible source;
- Forge is callable by ChatGPT in a real authenticated browser session;
- Watcher supplies a verified monitoring digest through a tested channel and Blind Sniper can route/track its findings;
- Shadow's review path and Ghost's provider-pool path are understood and their current availability honestly recorded;
- a real recurring trigger or self-owned automation performs the agreed foundation checks and reports success/failure to Ahmed;
- all gates are independently checked and remaining platform limitations are explicitly bounded.

Until then the status remains IN PROGRESS. No documentation-only milestone can declare the foundation complete.
