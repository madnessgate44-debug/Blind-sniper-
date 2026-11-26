# Blind Sniper capability evidence matrix (BS-001)

Base `f9cde15b20f9aaac6095eb45e727da0dbdee3104`. Static inventory; nothing run for this document. Status vocabulary: IMPLEMENTED+EXERCISED, FIXTURE-ONLY, PARTIAL, UNWIRED, ABSENT, UNKNOWN. "Tests" are `def test_` counts per test file from `tests/`. Live evidence is taken from audit #79 (https://github.com/madnessgate44-debug/Blind-sniper-/issues/79) and was not re-verified here.

| Capability | Source | Trigger path | Tests (methods) | Live evidence | Status |
|---|---|---|---|---|---|
| Model/provider call | `blind_sniper_model_worker.py` | daemon -> agent_runtime -> ModelWorker; CI provider smoke | model_worker 12, agent_runtime 17, provider_smoke 10 | Provider smoke run 45505263658: one synthetic keyless remote call (`baidu/ernie-5.5-flash-preview:free`) | IMPLEMENTED+EXERCISED (single synthetic call) |
| Independent agents / registry | `blind_sniper_runtime.py`, `chatgpt-home/runtime/agents.json` | runtime planner CLI; agent_runtime | orchestration 28, runtime 3, tool_runtime 13 | none live; registry validated by CI runtime workflow | FIXTURE-ONLY / PARTIAL: registry and dispatch exist; no multi-agent run observed |
| Durable queue/lease/recovery | `blind_sniper_worker.py`, `_queue_schemas.py` | daemon | worker 20, queue_schemas 20, worker_workflow 6 | worker workflow exists; no resident worker observed | FIXTURE-ONLY |
| Ledger (hash chain, GitHub store) | `blind_sniper_ledger.py` | worker, executor, browser_dispatch | ledger 21, github_ledger 25 | no private-repo round trip observed | FIXTURE-ONLY (fake GitHub API) |
| Executor | `blind_sniper_executor.py` | CI workflows | executor 14, executor_workflow 12, receipt 12 | executor workflows exist; run history not re-read here | IMPLEMENTED, CI-exercised per audit; UNKNOWN for current runs |
| Patch verify | `blind_sniper_forge_verify.py` | executor `forge-patch-verify` | forge_verify 6 | no run seen | FIXTURE-ONLY |
| Tool runtime | `blind_sniper_tool_runtime.py` | daemon -> agent_runtime | tool_runtime 13 | none live | FIXTURE-ONLY |
| Native browser | `blind_sniper_browser.py`, `_browser_dispatch.py`, `_mcp_server.py` | browser workflow, MCP stdio | browser 44, dispatch 9, mcp 17 | browser workflow runs per audit (real Chromium on CI against fixtures/one read-only live site smoke script exists) | IMPLEMENTED+EXERCISED on CI for fixtures; session persistence on a resident host UNKNOWN |
| Memory/private persistence | `blind_sniper_memory*.py`, `_handoff*` | daemon capture; handoff runtime | memory 13, handoff 7, knowledge 4, retrieval 3, runtime 2 | memory workflow on PR | FIXTURE-ONLY; `memory_retrieval` has no production importer |
| Autonomy | `blind_sniper_autonomy.py` | none wired | autonomy 6 | refuses unattended mode by design | PARTIAL / UNWIRED to daemon |
| Watcher | `blind_sniper_watcher.py` | none wired | watcher 4 | none | PARTIAL / UNWIRED |
| Connectors/OAuth/token refresh | none in code | none | none | none | ABSENT (a local unpushed registry branch exists, fake HTTP only) |
| Notifications | daemon writes an events file; no sender | none | covered inside daemon tests | none | ABSENT for delivery |
| Deployment/runtime availability | `api/health.py`, `vercel.json` | HTTP GET | vercel_health 4 | health returns 200, `task_execution_enabled=false`, `worker=not_activated` | health only; task execution ABSENT in deployment |
| REE | `.github/workflows/ree-wrapper-run.yml` | manual dispatch | none | runs 45596006799 fail, 45607329745 fail, 45608107720 success (artifact files unread) | external wrapper, not native |
| Local small-model proof | local diffs outside repo | n/a | 46 on a fresh clone plus patch (local) | one local run, 6 of 7 mutants killed | LOCAL ONLY, not in `main` |
| Browser/other smokes | `scripts/run_blind_sniper_*_smoke.py` | workflows | daemon_once_smoke 2 | daemon-once run 45587990290 (stub model) | stub/fixture |

## Limits
- Pass/fail counts are not re-run; the only count on record is the audit baseline (376 tests, 3 environmental errors, Python 3.10.12).
- "IMPLEMENTED+EXERCISED" here means a CI or sandbox run was reported, not that it is production-proven. No production task execution exists.
- Rows marked UNKNOWN need a fresh read of Actions run history; not done in this ticket.
- Workflow trigger details were counted by string match and should be re-read before use.
- Test method counts mix unit, fixture and simulation tests; the table does not separate them.
