# Blind Sniper — Software Company Capability Architecture

> **Owner architecture decision — 2026-11-27:** Codex and Blind Sniper are separate, independent projects running in parallel. Codex is not a Blind Sniper provider, executor, worker, subprocess, orchestration service, or task store. Blind Sniper is not a Codex dependency. Each project owns its own runtime, agents, skills, connectors, credentials, task state, memory, logs, and release lifecycle. They must reach equivalent capability parity, implemented and operated independently. ChatGPT requires two distinct, separately authenticated and independently revocable access paths. This architecture decision supersedes any older Codex-host-executor language in this document. See Issue #100 for the separate Codex access work.

**Work item:** BS-SOFTWARE-COMPANY-001 (#99)  
**Baseline:** `main` branch, refreshed 2026-11-27; exact HEAD is recorded on the associated PR.  
**Status:** Architecture proposal grounded in repository registries and open PR evidence. This is not a claim that every role runs as an independent process or that all connectors are operational.  
**Scope:** Native-first software-engineering company. Blind Sniper owns task state, orchestration, permissions, tools, execution, evidence and recovery. A model provider supplies inference only.

## 1. Executive determination

Blind Sniper already has a meaningful native specification and several runtime components, but it is not yet an autonomous software company in production.

- [V] The native roster contains **10 role contracts** in `chatgpt-home/runtime/agents.json`. Role contracts are not proof of ten separate model processes. The registry itself marks most roles as dependent on a host/worker; `shadow` explicitly lacks a verified independent execution identity.
- [V] There are **6 operating profiles** in `chatgpt-home/runtime/profiles.json`, **9 workflow contracts** in `chatgpt-home/runtime/workflows.json`, **14 native skill contracts** and **33 mirrored reference skill files** in `chatgpt-home/runtime/skills.index.json`.
- [V] The model invocation boundary exists in `scripts/blind_sniper_model_worker.py`; durable lifecycle/ledger code exists in `scripts/blind_sniper_runtime.py`, `scripts/blind_sniper_ledger.py` and `scripts/blind_sniper_worker.py`; the host daemon is `scripts/blind_sniper_daemon.py`; bounded tools are in `scripts/blind_sniper_tool_runtime.py`; browser code is in `scripts/blind_sniper_browser.py` and its dispatch/MCP adapters.
- [V] `chatgpt-home/runtime/EXECUTION_ENGINE.md` explicitly says the engine is not a distributed agent executor and that role contracts do not currently mean separate model processes. It also says the GitHub-backed ledger is mocked in tests and no live private-repository write was performed.
- [V] `chatgpt-home/runtime/README.md` says the daemon is not started by GitHub Actions and no approved host service is active; R5 remains partial.
- [V] Connector foundations #93, #103, #104, #109 and #110 are merged. #109 provides public unauthenticated GitHub reads only; #110 adds read-only Git permissions and an intentionally incomplete self-check. Merged code/tests are not proof of authenticated external integrations or daemon wiring.
- [U] A live, durable, unattended native task run with separate agent identities, verified private persistence, real browser session recovery, notifications, and production task execution has not been demonstrated by the inspected repository evidence.

**Conclusion:** retain the existing ten roles and six profiles. Do not add more named agents yet. Close the execution, permission, recovery and evidence gaps before expanding the roster.

## 2. Canonical role-to-capability matrix

| Company function | Canonical agent/profile | Required skills (native unless marked reference) | Required tools / connectors | Permission posture | Verification / current gap |
|---|---|---|---|---|---|
| Engineering manager / dispatcher | `blind-sniper`; profile `blind-sniper` | `agent-dispatch`, `owner-policy`, `multi-session-pr-coordination`, `blind-sniper-continuity`, `zero-cost-gate` | GitHub issues/PRs; native workflow and task lifecycle; model invocation | Observe by default; dispatch only allowlisted roles/tools; cannot expand Owner authority | [V] Registry and workflow contracts exist. [U] A continuously available dispatcher/worker and automatic cross-session callback are not proven. |
| Product / requirements analyst | `researcher` + `planner`; profile `research` | `web-research`, `github-research`, `prd-authoring`, `owner-brief`, `documentation-standards` | GitHub read; web research; Files where connected | Read-only; no product mutation | [V] Session-scoped research and PRD procedures exist. [U] Persistent autonomous discovery loop not proven. |
| Software architect | `planner` + read-only `reviewer`; profiles `research` / `review` | `architecture-and-adr` (reference mirror), `api-design` (reference mirror), `security-and-permissions`, `scope-discipline` | Repository source/registry inspection; GitHub; diagram/document tooling only when available | Read-only; architecture proposals separated from implementation | [V] Runtime and architecture registries exist. [U] No enforced architecture decision gate across all implementation tasks. |
| Implementation engineer(s) | `engineer`; profile `engineering` | `github-workspace`, `git-workflow`, `workflow-authoring`, `test-and-evidence`, `engineering-execution-os`, `secret-redaction-scan`, `zero-cost-gate`; select specialist reference skills only as needed | Native `repo.read_file`, `repo.write_file`, `verification.run`; isolated branch/worktree; model provider inference | Workspace-write only in task paths; policy/config/secret paths denied by default; no arbitrary shell | [V] Tool runtime and model boundary exist. [U] End-to-end host invocation and verified branch/PR publication by the native worker are not proven. |
| Independent code reviewer | `reviewer` + `shadow`; profile `review` | `code-review-rubric`, `test-and-evidence`, `security-threat-model`, `dependency-supply-chain`, `docs-evidence-format` | Read-only GitHub diff, CI logs, test artifacts | Read-only; reviewer must not share the implementer's mutable workspace or identity | [V] Review contracts and workflow exist. [U] `shadow` independent execution identity is explicitly unverified; same-model/same-context review must not be labelled independent. |
| QA / test engineering | `qa-verifier`; profiles `engineering` / `review` | `testing-strategy` (reference mirror), `test-and-evidence`, `accessibility-audit` (reference), `performance-engineering` (reference) | Fixed verification commands; CI; browser fixture workflow | Test-only; no production data or deploy rights | [V] CI tests and browser fixtures exist. [U] Production E2E and live multi-agent acceptance remain unproven. |
| Application security | `reviewer` + `shadow`; profile `review` | `security-and-permissions`, `security-threat-model`, `secret-redaction-scan`, `dependency-supply-chain`, `data-privacy-compliance` (reference) | Static analysis, dependency/security workflows, secret scanning; no credential-reading tool | Read-only; secrets are never model-visible; network egress deny-by-default | [V] Policy and redaction contracts exist. [U] A complete automated SAST/DAST/SCA gate and live egress enforcement are not established by current evidence. |
| SRE / release engineering | `release-manager` + `recovery` + `watcher`; profile `release` / `recovery` | `release-management`, `ci-cd-pipelines`, `observability`, `incident-response`, `sandbox-lifecycle`, `no-schedule-claims` (reference) | GitHub Actions; Vercel adapter only if connected; native health/receipt/rollback interfaces | Read-only until release gate; deploy/merge only after verified gates and within standing repo delegation | [V] Release and recovery contracts exist. [U] Resident service, alert delivery, incident automation and live rollback rehearsal are not proven. |
| Data / database engineering | `engineer` + `reviewer`; profile `engineering` / `review` | `database-migrations` (reference), `api-design` (reference), `security-and-permissions`, `test-and-evidence` | Native scoped file/test tools; database connector only after discovery, explicit scope and isolated test DB | No production data mutation; migrations require reviewed plan, backup/rollback and test environment | [V] Ledger/storage source exists. [U] No generic native database connector or production DB migration capability is verified. |
| Technical writing / documentation | `researcher` + `planner`; profile `research` | `documentation-standards`, `docs-evidence-format`, `owner-brief`, `engineering-execution-os` | GitHub docs/PRs; Notion/Canva only if action-level connection is confirmed and actually needed | Scoped docs write; never publish private memory/transcripts | [V] Docs workflows and evidence templates exist. [U] No automatic docs drift detector is proven. |
| Technical research / dependency analysis | `researcher`; profile `research` | `web-research`, `github-research`, `dependency-supply-chain`, `api-design` (reference) | Web, GitHub, package/vendor documentation | Read-only; cite primary sources; no package installation without engineering task | [V] Research tools available in this ChatGPT session. [U] Host-native research connector availability varies and is not implied. |

**Role cardinality rule:** these are functions, not a demand for eleven or more agents. A profile can compose several roles. Spawn a separate model invocation only where independent context, permissions or verification materially improve the result. Never call a role “independent” unless it has a distinct invocation/run ID, fresh context, separate permissions and correlated receipts.

## 3. Existing profiles and skills — what to keep

### Six profiles (canonical in `profiles.json`)
1. `blind-sniper` — dispatcher/operating lead; broad coordination, not unrestricted tool access.
2. `research` — read-only discovery and synthesis.
3. `engineering` — scoped workspace writes and fixed verification.
4. `review` — read-only review/security/QA.
5. `recovery` — continuity and task reconciliation.
6. `release` — read-only until release gates pass.

Do not create separate profiles for every language/framework. Add a specialist only after repository evidence shows a distinct permission boundary, toolchain or evaluation requirement.

### Fourteen native skills (canonical in `skills.index.json`)
`agent-dispatch`, `blind-sniper-continuity`, `browser-operations`, `codex-environment-maintenance`, `git-workflow`, `github-research`, `github-workspace`, `memory-and-continuity`, `multi-session-pr-coordination`, `owner-policy`, `security-and-permissions`, `test-and-evidence`, `web-research`, `workflow-authoring`.

The 33-file OpenHands mirror is reference material only. The index states that selected files must be explicitly retrieved; OpenHands keyword/path triggers do not execute natively. Keep this mirror out of the runtime dependency graph. Resolve the naming/path exceptions in the index before automating skill loading; do not silently assume every mirrored skill follows one path convention.

## 4. Connector and tool strategy

| Candidate | Purpose / data scope | Current status | Permissions and secret handling | Cost / fallback |
|---|---|---|---|---|
| GitHub | Issues, PRs, source, Actions, branches, release evidence | [V] Connected GitHub tools are callable in this ChatGPT session. [V] PRs #92–#97 propose native connector layers, but are not yet merged/integrated. | Separate read/write capabilities; repo allowlist; short-lived installation tokens where host integration is implemented; never log token values | [V] Existing GitHub repo is the control plane; no new service required. Fallback: current ChatGPT GitHub connector for this session only. |
| Vercel | Deployments, logs, project/runtime management | [U] Connector namespace/tool actions may exist, but account/project authorization and Blind Sniper host availability must be verified action-by-action. | Project-scoped token; deployment approval gate; redact environment values | Prefer existing free tier only after checking limits; fallback to GitHub Actions/health endpoint where sufficient. |
| Native browser | Browser navigation and approved UI actions | [V] Native browser adapter and MCP stdio source exist; CI/fixture evidence exists. [U] Persistent approved host session and production egress policy are not proven. | Domain allowlist, DNS/redirect/SSRF checks, explicit approval for click/fill/submit, isolated browser profile | Use web read/search for public read-only research; no third-party browser agent dependency. |
| Codex CLI bridge | Direct ChatGPT control of existing Codex host | [B] No direct ChatGPT-callable bridge verified. Issue #100 tracks feasibility and read-only bridge. | TLS, authenticated scoped tools, replay protection, strict schemas, allowlisted workspace/commands, redacted audit; no arbitrary shell | No paid host or second machine. If custom remote MCP is unavailable to this ChatGPT account, document the product limitation; do not claim GitHub comments are direct access. |
| External MCP connectors | Narrow external APIs needed by a task | [V] PRs #92–#97 define registry/contract/process isolation/GitHub read/self-check slices. [U] No complete authenticated, daemon-wired external connector stack is proven. | One connector = one manifest, explicit scopes, per-tool auth, timeouts, cancellation, egress allowlist, redaction | Add only when a real workflow needs it; local/mock test fallback; no generic unrestricted MCP proxy. |
| Database connector | Schema/query/migration work | [U] No verified generic DB connector in the current native registry. | Read-only by default; test DB writes only; production migration requires separate release gate | Use existing app/database tooling if present; do not add Supabase or another service by default. |
| Notion / Canva / Figma | Optional documentation/design integrations | [U] Tool namespaces are not proof of account authorization or host-native availability. | User/workspace-scoped OAuth; minimum permissions; no cross-workspace indexing | GitHub Markdown remains source of truth; use only when a concrete deliverable requires it. |

### Connector PR dependency order

- [V] #92 — registry/inventory foundation.
- [V] #93 — connector contract and cancellation.
- [V] #94 — process-isolated connector host, depends on #93.
- [V] #95 — Dependabot/CODEOWNERS/security configuration; not evidence of active Dependabot until merged and its first PR appears.
- [V] #96 — read-only public GitHub connector, depends on #94; public unauthenticated reads do not satisfy private-repo or write needs.
- [V] #97 — self-check on #96; latest reported result is explicitly incomplete, with git/terminal blocked by role permissions and terminal execution skipped.

**Decision:** do not merge this stack as if it were one working product. Review and land in dependency order only after each PR has exact-head CI, cancellation/timeout/redaction tests, least-privilege proof, daemon wiring, and an end-to-end receipt. A registry entry is not a live connector.

## 5. Security and execution contract

1. **Task authority:** every task binds task ID, repo, base SHA, allowed paths, role/profile, tool allowlist, time/resource limits, acceptance criteria and report destination. Task input cannot grant itself permissions.
2. **Provider boundary:** provider receives bounded context and inference requests only. It does not own orchestration, credentials, durable task state, retries, tools or acceptance.
3. **Tool policy:** tools are registered by schema and permission class. No arbitrary shell, unrestricted filesystem, arbitrary network or generic credential read. A model call must not bypass task leases.
4. **Isolation:** one writer per branch/worktree; read-only reviewer can run concurrently. Never share a mutable worktree between independent implementer/reviewer identities.
5. **Network:** deny by default; per-connector host allowlist; validate redirects, resolved IPs and DNS rebinding; enforce request size, timeout and response limits. Browser submit/fill/click are consequential operations.
6. **Secrets:** host-managed secret store only; never put values in issue bodies, task envelopes, CLI args, receipts, public files or model-visible dumps. Redact before logging.
7. **Durability:** persist claim, attempt, lease, checkpoint, tool receipt, model receipt, verification and terminal state. Recovery must reconcile actual artifacts and commit identity; never infer completion from a stale process.
8. **Verification:** code-writing agent cannot self-certify. Independent reviewer reads exact diff and exact-head CI logs. CI green is necessary, not sufficient for live integration.
9. **Release:** merge/deploy gate checks requirements, test matrix, security, dependency status, migration/rollback, health and post-release smoke. No auto-merge.
10. **Audit:** append-only receipt with task/run IDs, actor/role, base/head SHA, allowed tools, command, exit code, redacted output digest, timestamps and outcome.

## 6. Minimum enablement sequence (free-first)

| Order | Work | Acceptance gate |
|---|---|---|
| P0.1 | PR #91 intake crash-consistency review — **CLOSED / MERGED** | [V] Exact reviewed head `813a3e1183ec968dd8f4536e68129212672774f1` merged to main as `92f411c56a21f0b3eb2b7c8373aed9900b463e96`. Exact-head Runtime Registry and OS compliance jobs passed; offline persistence/fault-injection tests passed. This does not prove a live webhook or external agent execution. |
| P0.2 | Blind Sniper native runtime acceptance | [B] Native model/agent/worker/tool/browser capabilities exist at varying code maturity, but a live durable end-to-end task is not proven. Continue only within the native Blind Sniper runtime. |
| P0.3 | Independent Codex project access (#100) | [B] Separate project, not a Blind Sniper executor. Direct ChatGPT-callable access is not connected; zero-cost supported route and account eligibility must be proven before provisioning anything. Host/session and billing constraints remain. |
| P0.4 | ChatGPT ↔ Blind Sniper runtime access | [B] GitHub repository access is available in this ChatGPT session; direct callable access to the Blind Sniper native daemon/runtime is not proven. Build and test a separate, scoped access path without using Codex. |
| P0.5 | Durable native worker acceptance | Real host daemon run with opt-in task, checkpoint/restart, stale-lease recovery, private persistence round-trip and notification delivery; report Cloud Shell limits honestly. Codex CLI is a separate project and is not part of Blind Sniper's worker acceptance. |
| P1 | Connector foundations #93/#103/#104/#109/#110 | [V] These foundations are merged. Remaining work is daemon/runtime wiring, live authentication where needed, and end-to-end receipts; no connector is operational solely because its code is merged. |
| P1 | Independent agent evaluation | Two or more genuinely separate invocations with fresh contexts, distinct run IDs, constrained tools, correlated receipts; reviewer cannot share implementer context. |
| P1 | Security and QA gates | SAST/SCA/secret scanning, adversarial path/SSRF tests, permission-denial tests, regression suite, fixture and real-host separation. |
| P2 | SRE/operations | Health, structured logs, alert delivery, bounded retries, cancellation, rollback rehearsal and runbook. No unattended schedule until a real scheduler and receiver are demonstrated. |
| P2 | Specialist expansion | Add language/framework specialists only from observed repo stack and measured evaluation gaps. |

**No-card constraint:** do not provision a new paid service, card-backed API, external host or subscription. Reuse GitHub and the existing Cloud Shell host. Check current free-tier limits before relying on any external provider.

## 7. Explicit non-goals / prohibited shortcuts

- No Forge, OpenHands, TinyFish or third-party agent runtime as a core dependency.
- No Codex runtime dependency inside Blind Sniper; Codex remains a separate project with its own access and execution lifecycle.
- No second paid host or paid always-on worker.
- No Slack/Linear migration; GitHub remains the source of truth.
- No agent proliferation to make the roster look larger.
- No generic unrestricted MCP proxy or shell endpoint.
- No public memory/transcript/credential storage.
- No claim of 24/7 autonomy, independent agent execution, authenticated connector operation or production task execution without correlated live evidence.

## 8. Evidence sources and limits

- `chatgpt-home/runtime/agents.json` — canonical role roster and reference profiles.
- `chatgpt-home/runtime/profiles.json` — six profiles, sandbox postures and skill assignments.
- `chatgpt-home/runtime/workflows.json` — workflow triggers, adapter lists and execution-status labels.
- `chatgpt-home/runtime/skills.index.json` — 14 native skills and 33 mirrored reference skill files, activation rules.
- `chatgpt-home/runtime/README.md` and `EXECUTION_ENGINE.md` — model/tool boundary, daemon and ledger limitations.
- `chatgpt-home/tools/TOOL_REGISTRY.md` — tool inventory; parts of this document are stale relative to the current native-first policy and must not override `BLIND_SNIPER.md`.
- `chatgpt-home/BLIND_SNIPER.md` — authoritative native-first architecture and prohibition on Forge/OpenHands/TinyFish dependencies.
- PRs [#92](https://github.com/madnessgate44-debug/Blind-sniper-/pull/92), [#93](https://github.com/madnessgate44-debug/Blind-sniper-/pull/93), [#94](https://github.com/madnessgate44-debug/Blind-sniper-/pull/94), [#95](https://github.com/madnessgate44-debug/Blind-sniper-/pull/95), [#96](https://github.com/madnessgate44-debug/Blind-sniper-/pull/96), [#97](https://github.com/madnessgate44-debug/Blind-sniper-/pull/97) — open connector work, not merged operational capability.
- Issue [#100](https://github.com/madnessgate44-debug/Blind-sniper-/issues/100) — direct ChatGPT/Codex access blocker.
- Current baseline is the main SHA above. This document is an architecture synthesis, not an independent source-code audit or a runtime test report. PR #91 is now merged and recorded as closed; #98 is an accepted design awaiting implementation, not a live runner. Where evidence is not present, status is [U] or [B], not assumed complete.
