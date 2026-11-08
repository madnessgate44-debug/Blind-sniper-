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
8. Default to read-only and least privilege. Workspace writes require scoped authorization. Consequential operations require Owner approval.
9. No paid resource, credential rotation, secret mutation, merge, production deployment or permission expansion without explicit Owner approval.
10. Do not claim background execution unless a real trigger, runner, delivery route and successful run are verified.

## Execution modes

- **Native:** Blind Sniper executes in the current ChatGPT session using exposed tools.
- **Portable:** Task envelope and artifacts are persisted for another session or external worker.
- **Audited:** Isolated branch/worktree, independent review, test evidence and explicit approval gates for high-risk changes.

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
