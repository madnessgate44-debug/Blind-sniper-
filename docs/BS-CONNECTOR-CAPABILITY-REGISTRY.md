# Blind Sniper connector and capability registry (stage 0)

Base: main 79742ae2a640e86ad2ac636fee4c23d343203eae. Also compared against two in-flight local branches that are not on main: (1) BS-GH-INTAKE-001 / issue #90 (scripts/blind_sniper_github_intake.py and its test, Codex run in progress, no PR yet): an intake adapter from GitHub issues into the private task store, not a connector; (2) a parked model-task workflow (scripts/blind_sniper_model_receipt.py, .github/workflows/blind-sniper-model-task.yml, unreviewed, never dispatched). Neither adds a connector, tool or skill, so the inventory below is unchanged by them. Read-only inventory, no code changed. Written for the owner request of 2026-11-26 20:02 Cairo (connector and coding capability audit).

Status key: IMPLEMENTED (code and tests that exercise real behavior), PARTIAL, MISSING, BROKEN, UNVERIFIED (exists, no run or proof I could read). "Operational" for a connector means an authenticated integration test with Blind Sniper's own credential passed. None has.

Evidence classes: CI = Runtime Registry job log on 79742ae (Ran 449 tests, OK, skipped=1; Memory Tests 21 OK). Fixture = tests with stubs or synthetic data. Live = a workflow run on GitHub.

## A. Tools in the native tool runtime (https://github.com/madnessgate44-debug/Blind-sniper-/blob/79742ae2a640e86ad2ac636fee4c23d343203eae/scripts/blind_sniper_tool_runtime.py)

Exact inventory: 12 runtime tools in 3 families, 6 MCP tools. Runtime tools (TOOL definitions in the file): repo.read_file, repo.write_file, verification.run, agent.handoff, and 8 browser tools (navigate, snapshot, get_url, tabs, click, fill, press, screenshot). The MCP server (https://github.com/madnessgate44-debug/Blind-sniper-/blob/79742ae2a640e86ad2ac636fee4c23d343203eae/scripts/blind_sniper_mcp_server.py#L312) is separate: 6 tools (browser.start, resume, action, status, detach, close). Counts are not additive.

| Tool | Status | Evidence |
|---|---|---|
| repo.read_file | IMPLEMENTED | path jail (no .git, .env*, secrets, .ssh, no traversal), tests/test_blind_sniper_tool_runtime.py (Fixture, CI) |
| repo.write_file | IMPLEMENTED | needs allowed_paths and an explicit allowlist entry, same tests (Fixture, CI) |
| verification.run | IMPLEMENTED | fixed verification commands only (Fixture, CI) |
| agent.handoff | IMPLEMENTED | tool runtime + handoff tests (Fixture, CI) |
| browser.navigate/snapshot/get_url/tabs/click/fill/press/screenshot | PARTIAL | dispatch to scripts/blind_sniper_browser.py; Browser Adapter workflow runs on a hosted runner against fixtures; no authenticated session test; Playwright is not a declared dependency |
| terminal / git / ci / docs retrieval / vercel tools | MISSING | no tool definitions exist for them in the runtime |

## B. Connectors and MCP

| Item | Status | Evidence |
|---|---|---|
| Unified connector contract (tool interface, discovery, timeouts) | MISSING on main | no connector module in scripts/ on main. Credential loading from the environment exists in several modules (ledger, executor, model worker: BLIND_SNIPER_MODEL_API_KEY), but not behind one contract |
| Local unpushed branch feat/connector-registry (6b78cc5, on f9cde15) | PARTIAL, reviewed | Found in the local clone /tmp/bs, not on any remote. 1008-line scripts/blind_sniper_connectors.py plus 254-line tests; I ran the tests: Ran 7, OK. Contains: ConnectorSpec/ConnectorStatus, status verification with injected http (fake http in tests, no real API call ever made), env-secret redaction, role-based authorize() with scope and destructive-operation checks, a health report, persist/load, a CLI. Specs for github, google_drive, gmail, google_calendar, google_docs, google_sheets, whatsapp_business, model_gemini, browser, files, terminal. Gaps against the request: it is a status and authorization registry, not a tool contract (no call(), no timeouts per call, no discovery of tools, not wired into the tool runtime allowlist), its verifiers for files/terminal/browser are not exercised against the real runtime, and Gemini wrote it from synthetic prompts. Plan: stage 1 starts from this code (rebase onto main, review, wire to the runtime), not from scratch |
| MCP stdio server (browser only) | PARTIAL | scripts/blind_sniper_mcp_server.py: tools browser.start/resume/action/status/detach/close; tests/test_blind_sniper_mcp_server.py (Fixture). A live sandbox harness run is recorded in capabilities.json (2026-11-14), not re-verified. No ChatGPT-side invocation |
| GitHub | PARTIAL, one narrow authenticated capability proven | Proven live: the workflow-scoped secrets.GITHUB_TOKEN (contents:write only in the publish job, [blind-sniper-executor.yml#L127-L139](https://github.com/madnessgate44-debug/Blind-sniper-/blob/79742ae2a640e86ad2ac636fee4c23d343203eae/.github/workflows/blind-sniper-executor.yml#L127-L139)) published a correlated receipt to receipts/main, run 45870782524, 2026-11-26 17:48Z. This is one narrow write path inside Actions, not a GitHub connector: no issue, PR or checks API call from the native runtime is tested. Code path for a token from the environment: [blind_sniper_runtime.py#L624](https://github.com/madnessgate44-debug/Blind-sniper-/blob/79742ae2a640e86ad2ac636fee4c23d343203eae/scripts/blind_sniper_runtime.py#L624). The worker workflow reads secrets.BLIND_SNIPER_LEDGER_TOKEN ([blind-sniper-worker.yml#L71](https://github.com/madnessgate44-debug/Blind-sniper-/blob/79742ae2a640e86ad2ac636fee4c23d343203eae/.github/workflows/blind-sniper-worker.yml#L71)), but Settings > Secrets > Actions (read 20:04 Cairo, names only) shows "This repository has no secrets" and "This environment has no secrets". Account-level or inherited secrets were not checked separately (a personal-account repo has no organization secrets, but this was not confirmed in the UI). On the view I read, that workflow has no credential to use today. The earlier "scope unknown" wording is superseded: the secret is not configured, so there is no scope to verify. Not dispatched |
| Native filesystem, terminal, Git | PARTIAL | repo.* file tools only (A). No terminal or git tool |
| CI | PARTIAL | allowlisted executor (validate-runtime, run-tests, forge-patch-verify), durable workflow publishes receipts to receipts/main (live, test-only). No tool-level CI connector |
| Playwright | UNVERIFIED | browser adapter references Chromium; not a tool a model can call under a connector permission system |
| Documentation retrieval | MISSING | |
| Vercel | PARTIAL | health endpoint api/health.py deployed (served code static). No Vercel connector or deploy tool |
| Supabase, Render, Sentry, Notion, Google Drive, Figma | DESIGNED-ONLY (unsupported) | nothing implemented. They are registered as status `unsupported` with a named contract and required scopes, and no code that calls the service |
| Unified connector permission layer | MISSING | what exists and is IMPLEMENTED: per-task, per-tool native checks. [tool_runtime.py#L241](https://github.com/madnessgate44-debug/Blind-sniper-/blob/79742ae2a640e86ad2ac636fee4c23d343203eae/scripts/blind_sniper_tool_runtime.py#L241) validate_spec (repo.write_file requires allowlist entry and allowed_paths; browser write tools need an approval reference), [#L259](https://github.com/madnessgate44-debug/Blind-sniper-/blob/79742ae2a640e86ad2ac636fee4c23d343203eae/scripts/blind_sniper_tool_runtime.py#L259) _workspace_path (path jail), [daemon.py#L53](https://github.com/madnessgate44-debug/Blind-sniper-/blob/79742ae2a640e86ad2ac636fee4c23d343203eae/scripts/blind_sniper_daemon.py#L53) validate_host_policy (host policy, not task content, sets profile, tools, paths). Missing is one permission layer shared by connectors, not permission checks in general |
| Health checks | PARTIAL | daemon health.json (tasks map, 0600), api/health.py static 200; no per-connector health |
| Audit receipts | IMPLEMENTED (tools) | tool receipts with digests, receipt policy (tests/test_blind_sniper_receipt_policy.py). No connector receipts |
| Redaction | IMPLEMENTED | scripts/blind_sniper_redact.py, tests (Fixture, CI) |

## C. The twelve requested engineering skills

Existing skill assets are markdown, not executable, and are not Blind Sniper runtime code: chatgpt-home/skills (15 dirs, e.g. git-workflow, test-and-evidence, security-and-permissions, browser-operations, github-research, agent-dispatch), chatgpt-home/openhands-library/.agents/skills (33 skills imported from an OpenHands library; the owner now bars OpenHands dependencies), chatgpt-home/agents (13 role files), and scripts/find_skill.py and scripts/adapt_skill.py with tests/test_blind_sniper_skill_tooling.py.

| Skill | Existing asset | Status |
|---|---|---|
| repository reverse engineering | none | MISSING |
| software architecture | openhands architecture-and-adr (imported, external) | PARTIAL, needs a native rewrite |
| full-stack development | none | MISSING |
| debugging | none | MISSING |
| test engineering | chatgpt-home/skills/test-and-evidence, openhands testing-strategy | PARTIAL |
| security | chatgpt-home/skills/security-and-permissions, openhands security-threat-model | PARTIAL |
| browser QA | chatgpt-home/skills/browser-operations | PARTIAL |
| code review | openhands code-review-rubric, chatgpt-home/agents/reviewer.md | PARTIAL |
| deployment | openhands release-management | PARTIAL |
| documentation | openhands documentation-standards | PARTIAL |
| database engineering | openhands database-migrations | PARTIAL |
| task recovery | chatgpt-home/agents/recovery.md; queue lease recovery is real code (scripts/blind_sniper_worker.py, tests lease_recovery and contention) | PARTIAL: the runtime behavior is IMPLEMENTED, the skill document is not |

Skill loading into model prompts: UNVERIFIED. A grep for "skill" in blind_sniper_daemon.py, blind_sniper_model_worker.py and blind_sniper_agent_runtime.py returned nothing, so I found no loader there; I did not read every module, so this is not proof of absence.

## D. Preserved components (must not regress)

Native queue, leases, heartbeat and recovery (IMPLEMENTED, Fixture and multi-process tests, CI 449 tests). Model invocation boundary (IMPLEMENTED; live use: one keyless free-model smoke 2026-11-24 and a Qwen fixture slice, last live run failed before the receipt policy fix). Private memory (IMPLEMENTED, 21 tests). Daemon intake and health (IMPLEMENTED, PRs #84 to #89).

## E. Broken or unverified items

- Live local-model slice run 45861694992 failed; no post-fix live run exists.
- Three environment errors on Python 3.10 locally (tomllib, browser PermissionError); CI on 3.12 is green.
- Worker workflow: never run; it references secrets.BLIND_SNIPER_LEDGER_TOKEN, which the repository Settings view shows as not configured (inherited secrets not separately checked).
- No authenticated integration test exists for any connector.

## F. Prioritized plan (each stage separately mergeable and testable)

1. Connector contract, starting from the reviewed local branch feat/connector-registry (6b78cc5: rebase onto main, review, extend; do not rewrite) in scripts/blind_sniper_connectors.py. Add: a Connector base class (id, tools, required_scopes, health(), call()), a registry that is read-only to task content, discovery listing, and a hard rule that connectors are reachable only through the existing tool runtime allowlist and allowed_paths. Tests: discovery, unknown connector, permission denial, argument validation, timeout, redacted audit receipt. No network.
2. Native git and filesystem/terminal tools as the first connectors on that contract (bounded argv allowlist, workspace jail, no shell strings), with the same denial and timeout tests.
3. GitHub connector (issues, PRs, checks read first; writes behind an explicit per-task permission) using a token from the environment only. Operational only after one authenticated read test against this repository using a Blind Sniper held credential. The workflow GITHUB_TOKEN already proves a narrow Actions-side write. Whether a broader credential is needed is decided at stage 3 from the scopes the tests require; the repository currently holds no secrets, so any non-Actions credential must be added through GitHub's protected secrets UI, never in chat or the repo.
4. CI connector over stage 3 (workflow runs, logs), then documentation retrieval (allowlisted public hosts, size and redirect limits).
5. Playwright connector wrapping the existing browser adapter under the same contract, with browser QA skill tests.
6. Vercel connector (read-only deployment status first).
7. Skills: native, repo-owned skill files with a loader that injects only the skills a task names, and tests. Order: task recovery, test engineering, debugging, code review, security, repository reverse engineering, architecture, full-stack, browser QA, deployment, documentation, database. No OpenHands, Forge or TinyFish dependency, and no copied third-party text.
8. Optional adapters (Supabase, Render, Sentry, Notion, Google Drive, Figma): registered as designed-unsupported entries (contract and scopes written down, no service-calling code, no stubs) until each is separately approved and tested with an authenticated call.

Out of scope for every stage: paid services, new dependencies without justification, credentials in the repository.
