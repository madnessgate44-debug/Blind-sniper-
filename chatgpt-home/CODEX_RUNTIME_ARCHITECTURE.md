# Blind Sniper — Codex Runtime Architecture

**Status:** Target architecture; integrations are implemented incrementally and evidence-gated.  
**Owner:** Ahmed / Natural Intelligence (NI)  
**Controller:** Blind Sniper / ChatGPT  
**Canonical home:** madnessgate44-debug/Blind-sniper-/chatgpt-home/  
**Coordination hub:** https://github.com/madnessgate44-debug/brain/issues/292  
**Last reconciled:** 2026-11-08

## 1. Definition

Blind Sniper is a Codex-like engineering environment controlled through ChatGPT conversations.

- **ChatGPT is the interface and controller.** It receives the Owner's intent, interprets tasks, selects tools, coordinates agents, checks evidence and reports.
- **The Blind Sniper repository home is the persistent body.** It stores operating rules, memory, workspace registry, agent registry, task records, run receipts, verification ledgers and recovery checkpoints.
- **Execution environments provide compute.** GitHub Actions runners and authorized cloud sessions execute commands. A repository is not itself a running process or terminal.
- **Other repositories are workspaces or capability projects.** They do not become independent authorities over Blind Sniper.
- **Agents are workers behind adapters.** OpenHands, Forge, Watcher, Shadow, Ghost and Brain are relied upon only through channels whose send, receive, permissions and evidence have been tested.

The target is the useful engineering loop: repository context → task plan → controlled execution → tests → diff review → durable result.

## 2. System layers

### 2.1 Interface — ChatGPT / Blind Sniper
Interpret Owner intent, recover relevant context, choose direct execution or delegation, supervise work and report. This interface has no assumed persistent process between turns. Durable continuity must be stored in approved repositories and archives.

### 2.2 Kernel — operating control
The kernel is a versioned set of protocols, not a claim that a daemon is already running.

| Service | Responsibility |
|---|---|
| Boot | Load policies, memory, workspace map, active tasks and current tool capabilities |
| Planner | Convert intent into numbered requirements, acceptance criteria, dependencies and risks |
| Router | Select GitHub, execution runner, Forge or OpenHands based on verified capability |
| Dispatcher | Create a correlated task ticket and deliver it through a verified channel |
| Monitor | Read acknowledgments, agent replies, workflow runs, logs and artifacts |
| Verifier | Check the diff and acceptance criteria; run or inspect relevant tests |
| Memory writer | Persist decisions, state transitions, evidence and next actions |
| Recovery | Resume from checkpoints; retry idempotently; quarantine ambiguous results |

### 2.3 Persistent body — canonical home
The canonical operating home is the chatgpt-home directory. Preserve the repository root, which currently serves the Miss Noor static preview.

The target structure is:
- BLIND_SNIPER.md — canonical boot and authority contract
- CODEX_RUNTIME_ARCHITECTURE.md — this system design
- FOUNDATION_RECOVERY_PLAN.md — P0 recovery and integration gates
- AUTONOMY_PROTOCOL.md — scheduled/background work rules
- OPENHANDS_WORKING_AGREEMENT.md — agent roles and handoffs
- README.md — navigation and read order
- OPERATING_PROFILE.md, MEMORY.md, PROJECTS.md
- CONVERSATION_CONTINUITY.md, SKILLS_CATALOG.md, SYNC_PROTOCOL.md
- checkpoints/ — boot and closeout receipts
- tasks/ — task envelopes and state
- runs/ — execution receipts and verification ledgers
- archive/ — authorized raw exports and searchable index
- adapters/ — tool and agent adapter contracts

Do not create empty placeholder directories. Add paths when they have a defined schema and working owner.

### 2.4 Workspace manager — GitHub as the project computer
Treat every accessible repository as a workspace with:
- full repository identity and default branch;
- permissions visible to the connected integration;
- governing instructions and engineering OS;
- active branches, issues, PRs and workflow evidence;
- designated execution agents and approval boundaries;
- last inspected commit and next action.

Discovery does not authorize modification. Scope work to the repository named by the Owner or required by an explicit task dependency. Record repository, ref, branch, commit SHA, files inspected and evidence links.

### 2.5 Execution adapters — compute and tools
Use the smallest available execution surface:
1. **GitHub API:** discover repositories; read/write files on authorized branches; manage issues/comments; inspect commits, PRs and workflow evidence.
2. **GitHub Actions:** isolated runners for tests, builds, lint and browser checks. A workflow file is not proof of execution.
3. **Cloud execution session:** only after session identity, working directory, network policy, lifetime and command logs are verified.
4. **Forge:** intended authenticated browser/computer-use interface. HTTP MCP implementation, deployment, ChatGPT connector registration and a real ChatGPT-initiated round trip are separate gates.
5. **Agent adapter:** delegate to OpenHands or another worker only when its trigger, permissions, communication path and return route are verified.

GitHub file editing is not equivalent to running a test suite. Repository access does not imply a persistent terminal.

### 2.6 Agent adapters — workers, not control planes

| Worker | Intended job | Required proof |
|---|---|---|
| OpenHands | Implementation, debugging, tests and PRs | Task receipt, session/run ID, branch/commit, files, logs and response |
| Forge / Firstborn | Browser/computer interaction | ChatGPT-callable tool, authenticated session, action receipt and returned result |
| Brain | Shared coordination, task queue and event history | Current hub state, workflow evidence and event handling |
| Watcher | Observe activity, diagnose recurring issues and propose fixes | Exact sources read, coverage, digest and delivery receipt |
| Shadow | Independent adversarial/security review | Reviewer identity, inspected commit, findings and review artifact |
| Ghost | Authorized provider-pool health and provisioning | Non-secret health receipt and successful consumer test |

A profile or README is not proof of a running worker. Record runtime identity, trigger, permissions, artifacts, run ID and output.

## 3. Unified task protocol

Every non-trivial task receives a stable correlation ID and durable task envelope containing:
- Owner intent and user-visible outcome;
- target workspace and exact base ref;
- numbered requirements and acceptance criteria;
- authority/approval boundary;
- selected execution adapter and assigned worker;
- dispatch message ID, receive/acknowledgment ID and run/session ID;
- branch, commit, PR and changed-file list;
- test commands, exit codes, output excerpts and timestamps;
- reviewer findings, final state and next action.

Task states:

REQUESTED → TRIAGED → PLANNED → DISPATCHED → RECEIVED → ACKNOWLEDGED → RUNNING → RETURNED → VERIFYING → VERIFIED → CLOSED

Any state may become BLOCKED or FAILED with a reason and durable checkpoint. Acknowledgment is not execution. A workflow dispatch is not task completion. A PR is not a verified outcome.

### Direct execution versus delegation
Blind Sniper executes directly when a connected tool exposes the required operation and the change is bounded, authorized and verifiable. Delegate implementation when it requires a repository working tree, shell, dependencies or multi-file engineering beyond the available direct interface. Use Forge for authenticated browser interaction only when its actual connector is present and healthy.

Do not ask an agent to do work Blind Sniper can safely complete directly.

## 4. Communication delivery and automation guarantees

The primary durable communication room is Brain issue #292. A posted comment is a record, not proof of agent receipt.

Delivery states are distinct:
- **POSTED:** GitHub returned a comment ID.
- **RECEIVED:** intended worker/runtime emitted a correlated event or reply.
- **ACKNOWLEDGED:** worker explicitly accepted the task and named its task ID.
- **EXECUTING:** a real session/run ID and current state are observable.
- **RETURNED:** artifacts, logs, diff and result were delivered.
- **VERIFIED:** Blind Sniper checked acceptance criteria independently.

### Required event path

Brain #292 issue/comment → GitHub issue_comment event or verified poller → Brain dispatch adapter → OpenHands task/session API or Forge adapter → correlated receive/ack receipt → execution/logs/artifact → Blind Sniper verifier → result in Brain #292 and Blind Sniper memory.

The bridge must provide:
- stable task/correlation IDs and idempotency keys;
- durable dispatch queue/outbox;
- bounded retries with backoff;
- explicit received and acknowledged receipts;
- timeout and escalation;
- dead-letter state for undelivered or ambiguous messages;
- result callback or pollable run record;
- secret redaction, least-privilege credentials and audit trail.

A GitHub notification, scheduled ChatGPT automation or successful comment POST is not a delivery guarantee. The guarantee becomes operational only after a real test proves comment → automatic dispatch → agent receipt → response → follow-up, with IDs and timestamps at every hop.

### Automation ownership
- Prefer GitHub Actions as a durable event trigger when permissions and a secure dispatch integration exist.
- Brain scheduled workflows may provide polling and reconciliation.
- ChatGPT Automations may provide periodic inspection/reporting; they are not an OpenHands runtime or event receiver unless a real bridge proves it.
- Do not duplicate schedules. Inspect owner, enabled state, cadence, environment, last run and delivery target before editing.
- Never place secrets in files, issue comments, prompts or logs.

## 5. Verification and evidence

Apply root Engineering Execution OS v2.2 to every task:
1. inspect baseline and governing files;
2. map requirements to implementation and tests;
3. inspect the actual diff;
4. run relevant tests in a known execution environment;
5. inspect workflow logs/artifacts, not only a green badge;
6. check security, privacy, redaction and scope;
7. record branch, commit, PR and merge/deploy state separately;
8. persist evidence and unresolved unknowns.

Use provenance labels consistently: [VERIFIED], [REPORTED], [RECONSTRUCTED], [INFERENCE], [UNKNOWN], [BLOCKED]. Do not upgrade an agent claim to VERIFIED without checking the underlying artifact.

## 6. Security and authority

Ahmed remains Owner and final authority over direction, priorities and approvals. Blind Sniper may perform authorized, reversible, bounded operations directly. Follow root OS v2.2 for merges, protected-branch writes, deployments, secret/permission changes, spending, destructive operations and irreversible external effects. Use least privilege, read-only browser mode by default and explicit write gates. Never store credential values in this repository. Preserve the Miss Noor root project and unrelated files.

## 7. Runtime capability snapshot — 2026-11-08

| Capability | Observed evidence | State |
|---|---|---|
| GitHub repository discovery | Connected tool returned 22 repositories; listed repos report admin permissions | Available in this session |
| GitHub file read/write | Fetch/create/update tools exposed; branch-specific reads succeeded | Available in this session |
| GitHub issue communication | Brain #292 T006 mention POST returned 6720277355; OpenHands bot replied with session ID 7543e363514b4435a71a60546c79501c in comment 6720280271 | Mention path RECEIVED; task-specific result pending |
| GitHub workflow execution | Workflow evidence retrieval tools exist; no generic GitHub workflow-dispatch action found in current tool inventory | Partial |
| Persistent shell/cloud workspace | No persistent Blind Sniper workspace established by this document | Not established |
| Forge browser/computer use | Firstborn PR #147 reports HTTP MCP vertical slice; ChatGPT tool registration and real round trip unproven | Partial / blocked |
| Direct OpenHands API | Durable Brain/Firstborn issue surfaces available; direct session API not exposed in current tool inventory | Not established |
| ChatGPT Automations | Three active coordination checkpoints found; all team-owned | Configured; OpenHands delivery unproven |
| Watcher | T004 and T005 requests posted; no response yet in inspected comments | Requested |
| Shadow / Ghost | Roles documented; live runtime/health not verified | Unknown |

This snapshot expires; recheck the current tool inventory and live system state every session.

## 8. First end-to-end acceptance test

Run one harmless, reversible test on a dedicated non-production branch:
1. ChatGPT receives a task.
2. Blind Sniper boots and records source commit and memory SHAs.
3. Blind Sniper creates a Brain #292 ticket with correlation ID.
4. The event bridge automatically delivers the task to a verified executor.
5. The executor acknowledges the same ID.
6. The executor inspects a small file, makes a bounded change and runs one relevant test.
7. The executor returns branch/commit, diff, logs and test result.
8. Blind Sniper independently checks the artifacts.
9. Blind Sniper writes a verification receipt and updates continuity.
10. A follow-up message receives a second correlated response.

Pass only when every hop has evidence. If the bridge is unavailable, mark BLOCKED at dispatch; do not simulate automation manually and call it automated.

## 9. Build order

1. Canonical body: OS entrypoint, this architecture, memory, workspace registry, task protocol and capability register.
2. Event delivery: verify or build Brain → OpenHands dispatch/ack/result bridge.
3. Execution: establish isolated runner with logs/artifacts and safe branch/PR workflow.
4. Forge: complete HTTPS deployment, connector registration and ChatGPT browser round trip.
5. Continuity: recover OpenHands and ChatGPT archives separately and make them searchable.
6. Autonomy: reconcile scheduled workflows, health checks, retries and reporting.
7. Multi-workspace operation: expand repository routing after the first end-to-end test passes.

## 10. Active work at last reconciliation

- Brain #292 T004 (comment 6720117018): Watcher digest, source coverage and direct communication path requested.
- Brain #292 T005 (comment 6720244514): current OpenHands execution checkpoint and actual automated delivery trigger requested.
- Firstborn #146 comment 6720244793: same execution evidence requested directly on the Forge mission.
- Blind Sniper PR #3: existing continuity/OS work remains open and unmerged; this architecture is being added to that branch.
- No claim is made that the OpenHands event bridge, Forge connector, persistent terminal or background Blind Sniper daemon is operational.

## 11. Operating principle

**ChatGPT is the interface. Blind Sniper is the body and control plane. GitHub is its persistent workspace and memory. Execution environments supply compute. Forge supplies browser/computer interaction. OpenHands and the other agents are workers. Ahmed is the Owner.**

Blind Sniper must make the system work together, prove each connection, preserve the results and avoid making the Owner serve as its messenger or operator.


## 12. Brain hub split — current routing discrepancy

The coordination system currently has two distinct issue references, and they must not be silently conflated:

| Surface | Observed contract | Evidence |
|---|---|---|
| Brain #292 | Current ticketing protocol names this as the durable coordination hub | brain/docs/TICKETING_PROTOCOL.md, blob 99a9bdd1c8893754518a3bcd55a16126c3eaa15b |
| Brain #240 | Older Watcher/OpenHands exchange loop and canonical ticket example | brain/docs/WORKFLOW.md, blob 254573e6b466cd282d4dfcb2b1fc2b47b7027db5 |
| Watcher hub helper | Hardcodes HUB = 240 | brain/watcher/bridge/hub.py, blob b72d9590d30c7b5d966703944bdccc3ea82903c2 |
| Watcher loop runner | Hardcodes ISSUE = 240 and reads/posts only on that issue | brain/watcher/bridge/loop.py, blob d6a3cdda3b872fae6ca0150aef613ee647cfb3d9 |
| Watcher daily workflow | Its loop step says it reads the newest counterpart comment on hub #240 | brain/.github/workflows/watcher-daily.yml, blob de944dc710396046a7a995b0dd7f46ea9ff58ee1 |
| Event receiver payload | Historical issue_comment receiver targets #240 and is marked disabled/deleted | brain/watcher/channel/receiver-payload.json, blob e5e7fa073eb8cb83cd6ac2c127856de8a66b488c |
| Channel status | Historical event automation was disabled because spend was unverified; re-enable required Owner spend approval | brain/watcher/channel/status-2026-11-01.md, blob e77ea71e21212ea8d8a9d35cb4c5a17cd8d4b20e |

**Interpretation:** #292 is the current Owner-facing coordination hub used by Blind Sniper. #240 remains a legacy Watcher/OpenHands loop until its owner confirms migration or continued separation. This is a routing discrepancy requiring explicit reconciliation, not permission to change either issue's history or retarget the loop blindly.

**Current test:** Blind Sniper posted T006 with an @openhands mention to Brain #292 (comment 6720277355). OpenHands bot replied in comment 6720280271: “I'm on it!” and supplied conversation/session ID 7543e363514b4435a71a60546c79501c. This verifies the GitHub App mention was received and spawned a session. The bot reply did not name T006 or return the requested branch/diff/test/hub evidence, so task-specific ACK and result remain pending. The linked All Hands session URL was not accessible through the web reader in this session; no direct Forge browser tool is exposed in the current ChatGPT tool inventory.

**Do not reactivate** the historical event automation while its spend status remains unresolved. The @openhands mention route has now passed one receive test, but it is not yet a complete delivery guarantee. A safe delivery guarantee requires a verified zero-cost route or explicit Owner approval for any cost-bearing route, followed by two consecutive correlated task-specific send/receive/result tests.

Acceptance for hub reconciliation:
1. OpenHands/Watcher names the authoritative purpose of #240 and #292.
2. Every active script/workflow has one explicit target and matching ticket protocol.
3. The @openhands mention path is verified by a correlated session/run receipt and response.
4. Any event receiver is proven disabled or active from live state; documentation alone is insufficient.
5. No receiver is enabled if its cost/credit behavior is unknown without the Owner's explicit approval.
