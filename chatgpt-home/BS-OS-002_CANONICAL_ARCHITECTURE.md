# BS-OS-002 — Canonical Blind Sniper Architecture and Component Adoption Matrix

**Status:** Architecture blueprint — completed as a design artifact; implementation/adoption decisions remain gated by the next work items.  
**Repository:** `madnessgate44-debug/Blind-sniper-`  
**Design baseline:** branch `feat/bs-os-001a-registry-reconciliation-2026-11-09`, commit `38c07e82af17ceeb92d7dcccc58d96d72d5ed0f5`  
**Authority:** `AGENTS.md` → `ENGINEERING_EXECUTION_OS.md` v2.2 → `chatgpt-home/BLIND_SNIPER.md` v3.0 → current runtime registries and contracts.  
**Scope:** architecture and adoption decisions only. No runtime code, CI permissions, secrets, external services, paid resources, PRs, merges or deployments are changed by this document.

## 1. Outcome

Define one canonical, native-first architecture for Blind Sniper; identify the owner and activation boundary of each subsystem; distinguish existing implementation from design-only, partial, blocked and reference-only capabilities; and establish an evidence-gated order for selective component adoption.

**Architecture decision:** Blind Sniper's checked-in native policy, registries, workflow contracts, runtime state machine, ledger and verification rules remain the sole system of authority. External frameworks and services are optional, replaceable adapters. No imported source becomes active merely because it is present in the repository.

## 2. Current-state facts that constrain the design

1. The native roster is ten roles. Four additional profiles are reference-only and are not dispatchable.
2. Six operating profiles and 17 workflow registry entries are present. All workflow entries have an explicit contract mode; some are intentionally registry-only.
3. The native skill index contains 11 Blind Sniper skills and separately indexes 33 OpenHands mirror skill/rule files. Native skills are preferred; mirrored skills are explicitly retrieved and applied, not auto-triggered by OpenHands semantics.
4. `scripts/blind_sniper_runtime.py` is a registry-driven planner and guarded lifecycle state machine. It resolves workflow, profile, agent contracts, skill paths and adapter readiness; it persists and recovers task state. It does not spawn independent model processes.
5. `scripts/blind_sniper_ledger.py` provides local append-only event history, hash-chain validation and leases. The optional GitHub Contents adapter is mock-tested, refuses public repositories and has no verified live private-repository write target.
6. The runtime's common adapter contract defines capability discovery, dispatch, status, artifact retrieval, cancellation and callback. Those methods are interface requirements, not proof that every provider implements them.
7. GitHub Actions is available for configured events and CI. A bounded executor implementation is under draft PR #16 on a separate branch; it is not part of this architecture branch and has not passed independent review/closure.
8. Native browser code has recorded Chromium E2E evidence in CI, but it is not a persistent browser host and is not directly callable as a ChatGPT tool in this session. Persistent host provisioning is not verified.
9. OpenHands has one correlated read-only receipt in prior repository evidence; direct API dispatch/result retrieval and a repeatable code-artifact round trip are not established. Forge's connector is not registered as callable in this session.
10. The repository is public. Private continuity files in this repository are prohibited as personal-context sources. The proposed private-memory repository is not verified as created/private; private memory and transcript archive integration remain blocked.
11. The Owner's no-card/no-payment/no-paid-plan constraint is binding. Do not make core operation depend on paid infrastructure, a payment card or external spend.
12. `mattzcarey/claude-code-agent-framework` is an unavailable reference identity. By Owner decision it is excluded as a non-dependency; do not search for it again or substitute a nearby repository.

## 3. Canonical architecture

The architecture has six logical planes. These are responsibility boundaries, not claims that six daemons or independent model processes are running.

### 3.1 Authority and policy plane

**Owner:** repository root policies and `chatgpt-home/BLIND_SNIPER.md`.

- Defines mission, authority order, privacy boundary, zero-cost constraint, host limits and consequential-action approvals.
- The active ChatGPT host/tool contract remains the final enforcement boundary.
- Task envelopes, agent profiles, workflow files, imported skills and provider responses cannot grant themselves permissions.
- Default is read-only. Bounded branch writes are scoped to the named repository and branch. Merge, default-branch push, deployment, CI/CD permission changes, secrets, paid provisioning and destructive actions remain separate approval gates.
- No profile or adapter may weaken a higher-level policy.

### 3.2 Control and orchestration plane

**Owner:** `chatgpt-home/runtime/` registries and `scripts/blind_sniper_runtime.py`.

- `workflows.json` owns workflow routing, trigger declarations, agent assignments and contract modes.
- `profiles.json` owns operating profile purpose, allowed skills, allowed agents and workflow binding.
- `agents.json` owns the canonical ten-role roster, delegation contract and non-dispatchable reference profiles.
- `skills.index.json` owns native and mirrored skill inventory and activation semantics.
- The runtime resolves task → workflow → profile → agent contracts → skill references → required adapters.
- Do not add duplicate routing dictionaries to runtime code or maintain a second competing OS.

### 3.3 Capability and execution plane

**Owner:** `capabilities.json`, `ADAPTER_CONTRACT.md`, provider-specific adapters and the real host.

- An adapter is usable only when its tool is actually exposed, authenticated, authorized, within scope and able to return correlated status and artifacts.
- Provider capability states are operational facts, not marketing labels: available-in-session, partial, blocked/unregistered, reference-only, or not verified.
- GitHub Actions supplies bounded ephemeral compute for configured workflows. It is not a persistent interactive shell or general dispatch queue.
- The native browser adapter is a specialized CI/host capability. It does not establish an authenticated persistent browser service.
- OpenHands and Forge remain optional; their absence must not prevent boot, planning, direct GitHub operations, local task-state handling or verification.

### 3.4 Persistence and recovery plane

**Owner:** `scripts/blind_sniper_ledger.py`, runtime state schemas and approved private storage when available.

- The local JSONL ledger is the current native event-history implementation; the task JSON checkpoint is a convenience projection, not the authoritative event history.
- Hash-chain integrity detects edits but is not a signed/tamper-proof audit log.
- GitHub Contents CAS is optional and currently not operationally enabled against a verified private repository. Do not point it at this public repository.
- Task state, execution receipts and technical decisions may be stored in the public repository only when they contain no private personal/client data, secrets or raw transcripts.
- Private memory and raw transcript archives require a separately verified private storage boundary. Until then, do not read the prohibited public continuity copies or write private content here.

### 3.5 Verification and assurance plane

**Owner:** native QA/reviewer contracts, verification workflows, CI evidence and the Engineering Execution OS ledger.

- QA verifies acceptance criteria and test behavior; reviewer checks the implementation and evidence; release manager checks release conditions.
- A role name or reviewer field is not proof of a separate execution identity. Independent review is only established by a distinct, correlated review result whose artifact is retrieved and inspected.
- A green CI run proves only the checks actually executed in that run. It does not prove external integration, persistent hosting, production behavior or agent autonomy.
- Closure requires correlated task identity, exact commit, test commands and outputs, review result and all required acceptance criteria.
- No success state may be inferred from a posted message, acknowledgment, lease, planned task or workflow YAML.

### 3.6 Interface and continuity plane

**Owner:** ChatGPT conversation interface plus approved technical state anchors.

- ChatGPT is the conversational interface/controller for the current session; it is not a persistent daemon.
- `CURRENT_STATE.md` is the concise public technical-state anchor. `BUILD_PROGRESS.md` is historical/progress context and must not supersede current source files.
- The runtime registries and contracts are authoritative for system behavior; old architecture documents are subordinate when they conflict.
- Full ChatGPT transcript export is not exposed as a native capability here. Do not describe summaries or continuity notes as complete archives.

## 4. Component adoption matrix

| Capability / requirement | Canonical owner or source | Decision | Current evidence and gap | Security / activation boundary |
|---|---|---|---|---|
| Policy, authority, privacy, approvals | Root `AGENTS.md`, `ENGINEERING_EXECUTION_OS.md`, `BLIND_SNIPER.md` | **KEEP — canonical** | Present and controlling; actual host still enforces its own tool limits | Never allow lower-level contracts to expand authority |
| Workflow routing and orchestration | Native `workflows.json` + runtime | **KEEP — canonical** | 17 entries with explicit contract modes; runtime resolves registry rather than duplicate maps | Registry validation required after every change |
| Profiles and role roster | Native `profiles.json`, `agents.json` | **KEEP — canonical** | Six profiles; ten native roles; four reference-only profiles | Profile allowlists and host permissions remain authoritative |
| Native skills | `skills.index.json` + `chatgpt-home/skills/` | **KEEP — preferred** | 11 native skills indexed | Read the selected skill; index presence is not automatic execution |
| OpenHands skill/agent mirror | `chatgpt-home/openhands-library/` | **KEEP — pinned reference** | 68 intended files previously matched recorded upstream blobs; imported triggers do not execute in ChatGPT | Explicitly retrieve selected files; never install/execute mirror wholesale |
| Licensed harness imports | `source-library/0xenzyme__agent-harness`, `SUNRNEHUI__agent-harness`, `os-factory__har` | **KEEP — selective reference/adaptation** | Source files and license assets preserved; native adaptations exist | Preserve upstream license/attribution; host-compatibility review before activation |
| Ralph task decomposition and progress concepts | `snarktank/ralph` | **ADAPT — concepts only initially** | MIT license evidence recorded; PRD/story sizing, pass state and bounded progress are useful | Do not import its runner unchanged or bypass native approval, lease, ledger and verification gates |
| Claude Code Showcase patterns | `ChrisWiles/claude-code-showcase` | **REFERENCE ONLY** | Useful patterns; GitHub license metadata null and no root LICENSE detected; README MIT wording is not a complete license file | No verbatim code copying until license/permission is clarified; independently author compatible patterns |
| Mendelevium config | `mendelevium/claude-code-config` | **DO NOT ADOPT AS A DISTINCT SOURCE** | Same source lineage/tree as Showcase at inspected snapshot | Do not count it as an independent framework or duplicate components |
| Mattzcarey framework | `mattzcarey/claude-code-agent-framework` | **EXCLUDE — unavailable non-dependency** | Exact identity unavailable; Owner accepts it will not be identified | No further search; no substitute |
| Task envelope and receipts | Native runtime templates | **KEEP — canonical contract** | Task envelope and run receipt templates present | Inputs cannot select their own privilege profile; receipts require real correlated evidence |
| Task lifecycle and local persistence | Native runtime + JSONL ledger | **KEEP — canonical core** | Planner/state machine, leases, append-only events and recovery implemented/tested in repository history | Hash chain is not cryptographic signing; fail closed on invalid state |
| Remote durable ledger | GitHub Contents CAS adapter | **DEFER — private target gate** | Mock-tested; public-repository guard; no verified private target/live write | Do not create a private repository, token or secret without explicit authorization |
| Bounded executor | Native allowlisted executor proposal/PR #16 | **EVALUATE — separate review gate** | Draft PR #16 reports one real bounded job; awaiting independent review; not merged | Fixed command allowlist, minimal env, read-only token, isolated branch, artifact receipts; no arbitrary shell |
| General model-agent spawning | Native role contracts + provider adapters | **DO NOT CLAIM IMPLEMENTED** | Role contracts exist; runtime does not spawn separate model processes | Requires a real host/provider adapter with dispatch, status, artifacts, cancel and callback |
| OpenHands provider | `ADAPTER_CONTRACT.md` + capability registry | **OPTIONAL — partial** | One correlated read-only receipt; direct API and code-artifact return unproven | No core dependency; verify receive, task-correlated acknowledgment, execution and artifact return |
| Forge authenticated browser | Capability registry + native browser adapter boundary | **OPTIONAL — unavailable directly here** | Connector unregistered in this session; native browser CI path is not persistent | No credential/cookie transfer; host approval for writes; browser allowlist is not an OS firewall |
| Native browser CI | `scripts/blind_sniper_browser*.py` + browser workflow | **KEEP — bounded specialized adapter** | Two-cycle Chromium E2E evidence recorded; persistent host/cross-job recovery pending | Lease-gated actions, allowlisted operations, contained file IO, receipts; no authenticated profile support |
| Scheduled/background autonomy | Workflow registry + real trigger/receiver | **DEFER — no operational claim** | No verified generic dispatch receiver, persistent runner or reliable worker delivery | Must prove trigger → correlated execution → artifact → callback; cost and cadence bounded |
| Independent review | Reviewer/Shadow contracts + review receipts | **KEEP — gate; execution not proven** | Review contracts exist; distinct independent identity not verified | Reviewer must differ from implementer; metadata alone is not identity proof |
| Private memory and transcript archive | Verified private repository/storage (not yet established) | **BLOCKED — privacy gate** | Proposed private repo not verified; complete ChatGPT export unavailable | Never use public continuity copies as private memory; no private data in public repo |
| Release and deployment | Release profile/workflow + actual deployment host | **KEEP — gated** | Release contracts exist; deploy requires separate authorization and runtime evidence | No merge/deploy without explicit current-session approval |

## 5. Canonical task path

1. **Intake:** convert Owner intent into a stable task ID, outcome, repository/ref/base SHA, numbered requirements and acceptance criteria.
2. **Authority check:** resolve allowed paths, forbidden actions, approval requirements, privacy classification and zero-cost constraints. Reject self-selected privilege.
3. **Plan:** select one registered workflow, one host-approved profile, native agent contracts and only the skills needed.
4. **Readiness:** resolve each required adapter against the live session. If a required adapter is blocked, stop at the boundary or select a verified native alternative; do not simulate execution.
5. **Dispatch/execute:** use direct tools for bounded operations; use an adapter only when dispatch, status, artifact and callback paths are proven. Use an isolated branch for writes.
6. **Persist:** append correlated lifecycle and action receipts to the canonical ledger; keep secrets/private data out of public storage.
7. **Verify:** inspect exact changed files and diff; run relevant checks; retrieve raw outputs and artifacts; distinguish CI success from behavior and integration.
8. **Review:** obtain a distinct review result where required; reject self-review or uncorrelated reviewer claims.
9. **Close:** require all acceptance criteria, exact commit, test evidence, review result, blocker/unknown disclosure and repo/PR/deploy state.

## 6. Adoption rules and decision gates

A component may move from reference to adopted only when all conditions are satisfied:

1. **Identity:** exact upstream repository, revision and source lineage are known.
2. **License:** license metadata, root license file, README statements and explicit permission are recorded separately; required notices are preserved.
3. **Fit:** it fills a named requirement not already met by a native component.
4. **Host compatibility:** its trigger, runtime, APIs, dependencies and artifact return path work in the actual Blind Sniper host.
5. **Security:** least privilege, isolation, data boundaries, secret handling, outbound network, cost and failure modes are reviewed.
6. **Ownership:** exactly one canonical owner, registry entry, activation mechanism and source-of-truth path exist.
7. **Verification:** a bounded real acceptance test produces correlated run IDs, logs, artifacts and a reviewed result.
8. **Recovery:** interruption, retry, duplicate dispatch and failure behavior are defined and tested.

Failure of any gate leaves the component reference-only, partial or blocked. Do not duplicate a native subsystem just to mirror an upstream framework.

## 7. Dependency order after this blueprint

| Order | Work item | Deliverable | Entry condition |
|---:|---|---|---|
| 1 | **BS-OS-003 — Component adoption decisions** | Requirement-by-requirement reuse/adapt/defer/reject register, with source/license and acceptance gates | This architecture baseline accepted |
| 2 | **BS-OS-004 — Unified OS consolidation** | Reconciled authoritative architecture, boot sequence, current-state anchor and registries; retire conflicting historical wording | BS-OS-003 decisions stable |
| 3 | **BS-EXECUTION-001 — Execution engine completion** | One bounded, evidence-backed execution path; review/receipt/recovery integration | Architecture and adoption decisions stable; PR #16 independently reviewed/reconciled |
| 4 | **BS-INTEGRATION-001 — External integrations** | Per-provider end-to-end dispatch/status/artifact/callback proof or explicit exclusion | Provider is optional, authorized, zero-cost compliant and actually callable |
| 5 | **BS-RELEASE-001 — Production acceptance** | Requirement matrix, threat review, recovery test, release evidence and deployment decision | All mandatory capabilities pass; separate approval for merge/deploy |

Do not begin another generic executor rewrite before reviewing the existing native runtime and the bounded executor work already in PR #16. Do not make OpenHands, Forge, a private-memory repository or paid hosting a prerequisite for the native core.

## 8. BS-OS-002 requirement and acceptance mapping

| ID | Requirement | Acceptance criterion | Evidence / result |
|---|---|---|---|
| R1 | Establish authoritative policy and architecture ownership | Authority order and canonical owners are explicit; no competing OS is introduced | Root policy, `BLIND_SNIPER.md`, runtime registries inspected — **PASS** |
| R2 | Describe actual runtime boundaries | Planner/state machine, executor, adapters, persistence and agent-spawning limits are distinguished | `EXECUTION_ENGINE.md`, `ADAPTER_CONTRACT.md`, registries inspected — **PASS** |
| R3 | Evaluate available components | Every relevant native/imported/external component has a KEEP/ADAPT/REFERENCE/DEFER/EXCLUDE decision and boundary | Adoption matrix above — **PASS** |
| R4 | Resolve missing reference dependency | Missing Mattzcarey framework is excluded without substitution or further search | Owner decision plus source-library evidence — **PASS** |
| R5 | Define task and evidence flow | Lifecycle from intake through closeout, including correlation, receipts, review and recovery, is explicit | Canonical task path above — **PASS** |
| R6 | Respect privacy, cost and authority | Public/private boundary, no-card/no-paid rule and consequential-action gates are explicit | `BLIND_SNIPER.md` and root OS — **PASS** |
| R7 | Define dependency-ordered next work | Adoption precedes consolidation/engine completion; integrations and release are evidence-gated | Roadmap above — **PASS** |
| R8 | Validate implementation and runtime behavior | Architecture artifact is not represented as runtime acceptance | Runtime tests and new CI are **NOT RUN** for this documentation-only artifact |

## 9. Risks and unresolved gates

- **Executor review:** draft PR #16 is an existing implementation candidate, not an approved canonical executor. Independent review and branch-stack reconciliation are still required.
- **Private persistence:** no verified private repository exists in the inspected state; remote ledger writes and private continuity remain blocked.
- **Independent review identity:** native reviewer/Shadow contracts do not themselves prove separate execution.
- **External providers:** OpenHands and Forge are optional and not yet full end-to-end adapters in this session.
- **Persistent browser/runner:** no provisioned persistent host or cross-job recovery proof.
- **License uncertainty:** Showcase/Mendelevium implementation code remains reference-only pending license clarification.
- **Historical architecture drift:** `CODEX_RUNTIME_ARCHITECTURE.md` predates the current native-first policy and contains older coordination and persistence assumptions. It must be reconciled in BS-OS-004; until then this blueprint and the higher-authority current policies control wherever they conflict.
- **No runtime acceptance claimed:** this artifact defines architecture; it does not certify agent spawning, autonomous operation, private memory, external integrations or production readiness.

## 10. Explicit non-goals

- No code import from Showcase/Mendelevium.
- No substitution for the unavailable Mattzcarey source.
- No wholesale installation of OpenHands or Ralph.
- No permission bypass, arbitrary shell, unbounded loop or self-approval.
- No new paid service, payment-card dependency, account, secret, external receiver or persistent host.
- No private memory or raw transcript in this public repository.
- No PR creation, merge, default-branch push, CI permission expansion or deployment.

## 11. Evidence references

- Root policy: `AGENTS.md`, `ENGINEERING_EXECUTION_OS.md`
- Native authority: `chatgpt-home/BLIND_SNIPER.md`
- Current technical anchor: `chatgpt-home/CURRENT_STATE.md`
- Runtime source: `chatgpt-home/runtime/README.md`, `EXECUTION_ENGINE.md`, `ADAPTER_CONTRACT.md`
- Registries: `agents.json`, `profiles.json`, `workflows.json`, `capabilities.json`, `skills.index.json`
- Task contracts: `templates/TASK_ENVELOPE.json`, `templates/RUN_RECEIPT.json`
- Source provenance: `chatgpt-home/source-library/README.md`
- Existing architecture requiring reconciliation: `chatgpt-home/CODEX_RUNTIME_ARCHITECTURE.md`
- Draft bounded executor: [PR #16](https://github.com/madnessgate44-debug/Blind-sniper-/pull/16)

---
**Decision summary:** Keep Blind Sniper native-first. Adopt selectively, not wholesale. Treat all external workers as optional. Review the existing bounded executor before building another. Keep private memory and paid infrastructure out of the critical path. Prove every capability through a real correlated acceptance test.
