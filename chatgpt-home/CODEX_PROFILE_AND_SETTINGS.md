# Blind Sniper — Codex Profile and Runtime Settings Blueprint

**Status:** Research-informed design baseline; not yet an active Codex installation.
**Owner:** Ahmed / Natural Intelligence
**Profile owner:** Blind Sniper / ChatGPT
**Last reviewed:** 2026-11-08
**Purpose:** Define the operating profile, permission model, tool configuration, agent roles and lifecycle controls for the Codex-like environment hosted by this repository.

> Important boundary: this file specifies the target configuration. ChatGPT currently uses the tools exposed by its host; it does not read `~/.codex/config.toml`, run Codex CLI, or inherit Codex hooks merely because this file exists. The TOML below is a future Codex-host configuration template and must be validated against the installed Codex version before activation.

## 1. Research findings and design implications

The design is informed by these public implementations and references:

1. **OpenAI Codex configuration reference** — user-level `~/.codex/config.toml`, trusted-project `.codex/config.toml`, named profiles, sandbox modes, approval policy, permission profiles, MCP servers, hooks, agent roles, goals, memories and transcript persistence. Project-scoped settings are deliberately prevented from overriding several host-owned settings. https://learn.chatgpt.com/docs/config-file/config-reference
2. **OpenAI Codex CLI source** — supports selecting a profile, selecting a sandbox, choosing a working directory and using managed Git worktrees; dangerous full-access bypass is explicitly marked dangerous. https://github.com/openai/codex/blob/main/codex-rs/utils/cli/src/shared_options.rs
3. **Agent Harness (0xenzyme)** — adapter-driven control plane with Roadmap → Milestone → Goal → Task → Run → Evidence → State Sync, durable plans, dependency DAGs, candidate evidence and explicit human gates. https://github.com/0xenzyme/agent-harness
4. **HAR by os-factory** — isolated worktrees per agent, deterministic launch/verify/teardown, logs/artifacts and proof tied to a validated tree hash. https://github.com/os-factory/har
5. **Agent Harness (SUNRNEHUI)** — lightweight execution modes: native for current-session work, portable contracts for cross-session handoff, and audited mode for high-risk work. https://github.com/SUNRNEHUI/agent-harness
6. **Claude Code configuration examples** — separate project instructions, settings, MCP servers, hooks, skills, specialist agents and CI workflows; useful as a configuration-pattern reference, not as a schema to copy into Codex. https://github.com/mendelevium/claude-code-config

### Adopt

- Separate **identity/instructions**, **runtime settings**, **permissions**, **MCP/tool adapters**, **skills**, **agent profiles**, **task state**, **run evidence** and **project-local configuration**.
- Use the lightest execution path that satisfies the task: direct current-session work for small changes; durable task records for cross-agent or cross-session work; audited evidence for security, release, production and irreversible operations.
- Isolate concurrent workers in separate branches/worktrees. Never let two agents write to the same working tree concurrently without an explicit non-overlap proof.
- Make verification deterministic and attach it to the exact commit/tree tested.
- Treat agent outputs as candidate evidence until Blind Sniper validates them.
- Keep approval policy and trusted-project configuration outside any project that could self-authorize broader access.

### Do not copy blindly

- Do not enable full-access / bypass-permission modes as a convenience default.
- Do not assume Codex CLI config keys, Claude Code settings keys, or OpenHands microagent formats are interchangeable.
- Do not claim Codex features are available in this ChatGPT session unless the current tool inventory exposes them.
- Do not activate paid compute, paid APIs, event receivers or background automation without an established cost boundary and Owner authorization.

## 2. Identity and operating profiles

The primary identity is **Blind Sniper — AI Operating Lead**. It is not merely a coding persona; it owns the engineering control loop across repositories.

| Profile | Use | Default execution posture | Required output |
|---|---|---|---|
| `blind-sniper` | Default session and cross-repo coordination | Read-first; route only after capability and authority checks | Task plan, selected tools, durable state and closeout |
| `research` | Architecture, GitHub precedent, documentation, options | Read-only | Sources, comparisons, confidence and recommendation |
| `engineering` | Implement bounded changes | Workspace-write in isolated branch/worktree; tests required | Diff, exact commands, exit codes, artifacts |
| `review` | Independent code/security/requirements audit | Read-only | Findings ranked by severity, file/line evidence |
| `recovery` | Restore continuity, archives, failed delivery and agent state | Read-only first; write only to recovery branch | Provenance, coverage, reconciliation and recovery receipt |
| `release` | Merge, deploy, production or irreversible work | Plan and inspect first; explicit Owner approval for consequential gates | Release checklist, approvals, rollback and post-release verification |

Profiles are operational modes, not different identities. Blind Sniper remains the controller and records which profile governed each task.

## 3. Permission tiers

Use four explicit permission tiers. The default is Tier 0.

| Tier | Name | Allowed | Not allowed without escalation |
|---|---|---|---|
| 0 | Observe | Read repositories, issues, PRs, logs, docs; inspect status | Any mutation |
| 1 | Workspace write | Create feature branches, edit scoped files, commit, open/update PRs, run non-cost-bearing tests | Merge, production deploy, secrets, permission changes, spend |
| 2 | Consequential | Merge protected changes, deploy, change integrations/permissions, alter production data | Only with explicit Owner approval and recorded scope |
| 3 | Prohibited by default | Destructive or irreversible action, secret disclosure, unrestricted host access, unbounded spend | Requires a separate explicit Owner decision and platform permission; otherwise refuse |

**Rules**
- Start at Tier 0 and elevate only for the specific task.
- Tier 1 writes must be scoped to the named repository and feature branch. Do not treat the 22-repository inventory as blanket authorization.
- Deny secret reads and writes to `.env*`, credential stores and private key material unless a narrowly defined authorized operation requires a secure secret manager; never print secret values.
- Never use `danger-full-access`, `--yolo` or bypass-approval modes as the normal profile.
- External side effects, spending, production access, merge and deployment remain explicit Owner gates.
- An agent's own profile or a GitHub issue mention cannot elevate its authority.

## 4. Runtime settings that Blind Sniper needs

| Setting group | Required behavior | Why it matters | Implementation home |
|---|---|---|---|
| Model/reasoning | Host-supported model; higher effort for architecture, debugging and audit; efficient setting for routine reads | Balance quality, latency and cost | Host-level profile |
| Instructions | Canonical identity, authority order, boot, engineering lifecycle and evidence policy | Keeps behavior consistent | `BLIND_SNIPER.md`, root `AGENTS.md` |
| Workspace discovery | Enumerate repos; record default branch, permissions, instructions, active work and last inspected SHA | GitHub is the workspace computer | `REPOSITORY_REGISTRY.md` |
| Workspace trust | Explicit trust per repo/path; untrusted projects load no project-level hooks/config | Prevent project self-authorization | Host policy + registry |
| Sandbox | Read-only by default; workspace-write only for scoped execution; no danger-full-access default | Limits blast radius | Host sandbox/permission profile |
| Approval | On-request; ask at owner-only gates; deny unsafe operations | Preserves Owner authority | Host approval policy + OS |
| Agent roster | Explicit specialist roles, capabilities, constraints and return schema | Prevents vague delegation | Agent registry + adapter configs |
| MCP/tool servers | Named endpoints, health checks, tool allowlists, per-tool approval and timeouts | Provides browser, repository and orchestration capabilities | Host MCP config + adapter registry |
| Hooks | Session boot, pre-write policy check, post-tool evidence, subagent lifecycle, session closeout | Makes process repeatable | Host hooks + scripts when runtime supports them |
| Memory/history | Durable transcripts or authorized exports, searchable indexes, source IDs, checksums and retention | Prevents context loss | `MEMORY.md`, `archive/`, task/run receipts |
| Goals/tasks | Persistent goal, task dependencies, execution attempts and explicit completion | Enables cross-session continuity | `tasks/`, `runs/` |
| Worktree isolation | One isolated branch/worktree per concurrent writer; cleanup only after artifacts are preserved | Prevents collisions and protects baseline | Runner adapter |
| Verification | Repo-specific lint/test/build/E2E and exact tested SHA | Makes claims auditable | CI + verification receipts |
| Observability | Correlation IDs, run IDs, timestamps, redacted logs, artifacts and status callbacks | Diagnoses silent failures | `runs/`, Brain hub |
| Cost controls | Budget ceiling, provider/model allowlist, concurrency, retry cap, timeouts and spend receipts | Avoids unapproved spend | Runner/provider policy |
| Autonomy | Trigger, schedule, owner, delivery route, retry and failure alert all verified | Enables work between chats without pretending GitHub is a daemon | `AUTONOMY_PROTOCOL.md` |

## 5. Agent roster and contracts

| Agent | Assigned role | May do | Must return |
|---|---|---|---|
| Blind Sniper | Controller / orchestrator | Intake, inspect, plan, route, supervise, verify and synchronize | Owner-facing decision and evidence report |
| OpenHands | Engineering executor | Implement, debug, run tests and open PRs on assigned scope | Correlation ID, session ID, repo/branch/HEAD, diff, commands, exit codes, artifacts, blockers |
| Forge / Firstborn | Browser/computer-use executor | Navigate authenticated websites and operate approved browser workflows | Tool-call receipt, target URL, action log, redacted result, session cleanup |
| Watcher | Observer / systems analyst | Read activity, cluster failures, identify root causes and recommend bounded work | Coverage map, evidence links, ranked issues and digest |
| Shadow | Independent reviewer | Challenge assumptions, inspect diffs and threat model | Independent findings tied to exact commit |
| Ghost | Provider-pool custodian | Report authorized provider/model health and issue short-lived authorized access to workers | Non-secret availability/health receipt and consumer test |
| Brain | Coordination control plane | Durable ticketing, queue, event routing, schedules and archive indexes | Event IDs, workflow/run IDs, delivery state and output link |

No profile text proves that an agent is live. A role becomes operational only after a send/receive/result test and evidence of its current permissions.

## 6. Lifecycle hooks and deterministic controls

When the selected runtime supports hooks, implement these event contracts. Hook scripts must be versioned, reviewed and tested; never install untrusted hooks from a project automatically.

| Event | Hook responsibility | Failure behavior |
|---|---|---|
| SessionStart | Load canonical OS, memory index, active tasks, repository map and tool capability snapshot | Mark boot PARTIAL and stop writes if controlling rules unavailable |
| UserPromptSubmit | Classify intent, resolve project/task, check for existing task and authority boundary | Ask only for a genuinely missing essential detail |
| PreToolUse | Validate repository scope, permission tier, branch protection and prohibited targets | Block out-of-scope or prohibited mutation |
| PermissionRequest | Surface exact operation, scope, impact and reason for approval | Wait for Owner; never infer consent |
| PostToolUse | Record tool name, arguments summary, result reference, timestamp and correlation ID; redact secrets | Mark evidence missing if receipt cannot be stored |
| SubagentStart | Record agent identity, task ID, branch/worktree and allowed scope | Do not start without a task contract |
| SubagentStop | Collect result, artifacts, changed paths and test evidence | Treat missing result as incomplete |
| PreCompact / PostCompact | Preserve task state, decisions, open questions and evidence references | Do not discard the only copy of active work |
| Stop / SessionEnd | Run verification/closeout, update task and continuity records, report blockers | Do not mark task CLOSED if evidence or sync is missing |

Hooks should be deterministic policy enforcement, not another place to hide broad prompt instructions. The instructions belong in versioned Markdown; hooks enforce invariants.

## 7. Codex-host configuration template

This is a **starter template for a future Codex CLI host**, not an active configuration for this ChatGPT session. Validate key names and profile schema against the installed Codex version and its published schema before enabling. Use the user-level `$CODEX_HOME/config.toml` for host-wide settings and profile selection; use project `.codex/config.toml` only for trusted, project-specific overrides. Keep authentication and secrets outside Git.

```toml
#:schema https://developers.openai.com/codex/config-schema.json

# Conservative interactive default
approval_policy = "on-request"
sandbox_mode = "read-only"
web_search = "live"
model = "gpt-6"

[history]
persistence = "save-all"

[features]
goals = true
multi_agent = true
hooks = true
memories = true

[agents]
enabled = true
max_concurrent_threads_per_session = 3

[profiles.blind-sniper]
# Keep the default session conservative; elevate per task only.
approval_policy = "on-request"
sandbox_mode = "read-only"

[profiles.engineering]
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[profiles.review]
approval_policy = "on-request"
sandbox_mode = "read-only"

[profiles.recovery]
approval_policy = "on-request"
sandbox_mode = "read-only"
```

**Important validation note:** Codex supports named profiles in `config.toml` and separate profile config files selected with `--profile`. The exact profile inheritance/override shape must be checked against the current schema before this sample is treated as executable. This sample intentionally omits model IDs that may not be available to the signed-in account; replace `gpt-6` only with a currently advertised model ID.

### 7.1 Future MCP adapter pattern

Only register an endpoint after HTTPS, authentication, tool allowlists and an end-to-end connection test are proven. Example shape (values are intentionally symbolic):

```toml
[mcp_servers.forge]
enabled = false # enable only after public HTTPS + ChatGPT/Codex client test
url = "https://<verified-forge-host>/mcp"
bearer_token_env_var = "FORGE_MCP_TOKEN"
default_tools_approval_mode = "prompt"
tool_timeout_sec = 60
# enabled_tools = ["browser_status", "browser_navigate", "browser_screenshot"]
```

Never put a real bearer token in this file. Start with read-only tools; enable browser writes individually after tests. A ChatGPT connector and a Codex CLI MCP client are separate registrations and must be tested separately.

## 8. How configuration is applied

1. **Canonical instructions first:** root `AGENTS.md` and Engineering Execution OS govern all repositories; Blind Sniper-specific instructions live under `chatgpt-home/`.
2. **Host-level profile second:** a future Codex host loads user-level `config.toml` from `$CODEX_HOME`. This is where model selection, approval, sandbox defaults, MCP endpoints and host-wide agent settings belong.
3. **Project-level configuration third:** a repository may provide `.codex/config.toml` and `AGENTS.md` only after its trust status is explicitly established. Project config must not override host authentication, profile selection or global policy.
4. **Task-level elevation:** select the appropriate profile and permission tier for the task. Elevation applies only to the named repository, branch and duration.
5. **Runtime validation:** inspect the effective configuration, available tools, sandbox behavior, MCP health and runner identity. Do not infer effective settings from a checked-in file.
6. **Evidence and rollback:** record the active profile, policy version, tool inventory, run ID and exact changed settings. Revert a configuration change if validation fails.

For the current ChatGPT-native implementation, the equivalent is: load the canonical Markdown profile at boot, use the connected GitHub/other tools only as exposed, enforce the permission tiers in task routing, and record every tool call's outcome in the task/run receipt. This is a behavioral implementation until a real Codex host and runner are attached.

## 9. Minimum acceptance tests before calling the profile operational

- [ ] Boot reads canonical instructions and records their current SHAs.
- [ ] Unknown repository defaults to read-only and requires inspection before mutation.
- [ ] Tier 1 can edit a dedicated feature branch but cannot merge or deploy.
- [ ] Secret files and credential values are not returned in logs or memory.
- [ ] Each concurrent worker receives an isolated worktree or is serialized.
- [ ] OpenHands task dispatch, acknowledgment, result and artifact return share one correlation ID.
- [ ] Forge endpoint authenticates, rejects missing credentials and exposes only allowlisted tools.
- [ ] Hook failure blocks unsafe mutation and produces a diagnostic receipt.
- [ ] Test results are bound to the exact commit/tree SHA.
- [ ] Session closeout persists decisions, task state and next action.
- [ ] Cost-bearing operations remain blocked without explicit Owner approval.
- [ ] A second session can resume a task from the persisted state without asking the Owner to repeat known details.

Until these tests pass, the profile status remains **DESIGNED / PARTIALLY IMPLEMENTED**, never VERIFIED as a complete Codex runtime.

## 10. Research links

- OpenAI Codex configuration: https://learn.chatgpt.com/docs/config-file/config-reference
- OpenAI Codex CLI source: https://github.com/openai/codex
- Agent Harness (0xenzyme): https://github.com/0xenzyme/agent-harness
- HAR: https://github.com/os-factory/har
- Agent Harness (SUNRNEHUI): https://github.com/SUNRNEHUI/agent-harness
- Claude Code config showcase: https://github.com/mendelevium/claude-code-config
