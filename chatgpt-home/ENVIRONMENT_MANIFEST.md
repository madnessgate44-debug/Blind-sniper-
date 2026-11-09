# Blind Sniper Agent Environment — Manifest

**Version:** 1.0.0  
**Status:** Implemented as a GitHub-backed specification and asset library; runtime adapters remain capability-gated.  
**Owner:** Ahmed (NI)  
**Operating lead:** Blind Sniper (AI)

## Architecture

| Layer | Canonical location | Purpose | Runtime truth |
|---|---|---|---|
| Identity and policy | `BLIND_SNIPER.md`, `BLIND_SNIPER_OS.md`, root `ENGINEERING_EXECUTION_OS.md` | Role, authority, lifecycle and safety | Instructions apply when loaded in ChatGPT |
| Host profiles | `CODEX_PROFILE_AND_SETTINGS.md`, `config/` | Codex-compatible settings templates | Templates only until installed in a real Codex host |
| Skills | `skills/` | Reusable procedures and acceptance gates | ChatGPT reads/uses selected skill; no automatic loader claim |
| Agents | `agents/` | Specialist contracts and handoff formats | Roles can be invoked by Blind Sniper; independent execution requires a real adapter |
| Tools | `tools/TOOL_REGISTRY.md` | Capability, auth, risk and availability registry | Only currently exposed tools are callable |
| Workflows | `workflows/` | Deterministic lifecycle and automation contracts | Manual/current-session or actual CI/automation only |
| Templates | `templates/` | Standard task, plan, review, run and closure artifacts | Copy into task records |
| Runtime adapters | `runtime/` | Dispatch, execution, evidence and callback contracts | Adapter status is tracked per integration |
| Lifecycle hooks | `hooks/` | Session, tool, permission and sub-agent guards | Contracts only unless a host executes them |
| MCP/browser | `mcp/` | Server registry, browser boundary and activation gates | Forge connector remains blocked until verified deployment and registration |
| Memory | `MEMORY.md`, `PROJECTS.md`, `CONVERSATION_CONTINUITY.md`, `checkpoints/` | Durable state and decisions | GitHub-backed; not a verbatim ChatGPT transcript archive |
| Imported references | `openhands-library/` | Source-preserving OpenHands skill/agent/hook mirror | Reference only; no OpenHands loader runs inside ChatGPT |

## Design rules

1. Use source-preserving imports only when license and provenance permit; otherwise implement an independently authored equivalent.
2. Every skill has triggers, prerequisites, permitted tools, procedure, outputs, verification and failure handling.
3. Every agent has a narrow role, explicit authority, inputs, outputs, prohibited actions and escalation path.
4. Every tool has a live availability state. Documentation is not an installed connector.
5. Every workflow has entry conditions, states, idempotency, retries, timeout, evidence and stop conditions.
6. Every run is correlated to a task ID, repository, base SHA, worker/session ID and resulting SHA.
7. Isolate concurrent writes by branch/worktree. Never have two agents mutate one working tree concurrently.
8. Default to read-only outside an active delegation. Within madnessgate44-debug/Blind-sniper-, the standing Owner delegation authorizes scoped repository writes, pushes, PR merges, CI/CD edits and eligible deployments without repeat approval; retain least privilege. The native runtime policy mirror is chatgpt-home/runtime/authority.json.
9. No paid resource, credential rotation, secret mutation/disclosure or permission expansion. Merges and production deployments are permitted only within the active repository delegation and after the release gate passes.
10. Do not claim background execution unless a real trigger, runner, delivery route and successful run are verified.

## Execution modes

- **Native:** Blind Sniper executes in the current ChatGPT session using exposed tools.
- **Portable:** Task envelope and artifacts are persisted for another session or external worker.
- **Audited:** Isolated branch/worktree, independent review, test evidence and either active standing delegation or explicit Owner approval for high-risk changes.

## Readiness gates

- [x] Core operating identity, policy and profile blueprint exist.
- [x] OpenHands reference library mirror exists (68 files; see import manifest).
- [x] Skill and agent contracts defined in this environment.
- [x] Tool registry distinguishes callable host tools from unavailable adapters.
- [x] Workflow and artifact templates defined.
- [ ] Generic isolated execution runner available and verified.
- [ ] Forge public HTTPS MCP endpoint and ChatGPT connector round trip verified.
- [ ] OpenHands task-specific session result retrieval verified.
- [ ] Two consecutive end-to-end task round trips verified.
- [ ] Full Codex host installation performed on a host that can run Codex CLI.

A checked item means only the evidence described in the linked files; this manifest is not a blanket runtime readiness claim.


## 2026-11-08 implementation checkpoint

- [x] Nine native skills created with metadata, trigger, permission, procedure, evidence and failure contracts.
- [x] Nine specialist agent contracts created (researcher, planner, engineer, reviewer, QA verifier, recovery, watcher, shadow, release manager).
- [x] Five workflow contracts created (session boot, task lifecycle, handoff, closeout, release gate).
- [x] Four reusable templates created (agent task, verification ledger, review report, run receipt).
- [x] Tool registry, lifecycle hook/guard contract, MCP/browser integration contract and common runtime adapter contract created.
- [x] Six Codex host profile templates created (base, Blind Sniper, research, engineering, review, recovery).
- [x] GitHub Actions structural validation executed successfully on branch head 1a70c10f3d49b67f51986ba383b2c7abbde1fba3: run 42473260867, job validate-environment, PASS: 39 required assets, 9 skill contracts, credential-pattern scan clean.
- [x] Engineering Execution OS compliance also passed on the same commit: run 42473260744, job policy-compliance.

**Boundary:** These checks validate repository assets and policy structure. They do not prove Codex CLI installation, ChatGPT hook execution, browser MCP connectivity, OpenHands result retrieval, isolated shell execution or full external-agent round trips. Those remain open readiness gates.

## 2026-11-09 registry reconciliation

The 2026-11-08 implementation checkpoint above is a historical snapshot, not the current catalog. The reconciled runtime index now records:

- 11 native skill contracts, including `blind-sniper-continuity` and `github-research`.
- 10 canonical native agent roles and 4 additional reference-only profiles; reference profiles are not dispatchable.
- 17 workflow registry entries: 11 entries reference 9 markdown contracts and 6 are intentionally registry-only with explicit reasons.
- 33 OpenHands skill/rule files remain a separate source-preserving mirror; they are not counted as native skills and are not automatically activated.

The current source of truth is `runtime/agents.json`, `runtime/skills.index.json`, `runtime/workflows.json` and their corresponding README/catalog files.