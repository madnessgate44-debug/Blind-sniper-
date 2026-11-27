# Blind Sniper capability evidence matrix (BS-001)

Base `f9cde15b20f9aaac6095eb45e727da0dbdee3104`. Static inventory; the document author ran no tests. CI evidence below was read from GitHub Actions at the PR head. Status vocabulary: IMPLEMENTED+EXERCISED, FIXTURE-ONLY, PARTIAL, UNWIRED, ABSENT, UNKNOWN. "Tests" are `def test_` counts per test file from `tests/`. The Live evidence column is historical audit #79 evidence (https://github.com/madnessgate44-debug/Blind-sniper-/issues/79), not re-verified, except where a row says CI re-verified. Only the CI, simulation and test-count statements in the Limits section were re-verified against current-head CI. No row is verified against a live model or production path.

| Capability | Source | Trigger path | Tests (methods) | Live evidence | Status |
|---|---|---|---|---|---|
| Model/provider call | `blind_sniper_model_worker.py` | daemon -> agent_runtime -> ModelWorker; CI provider smoke | model_worker 12, agent_runtime 17, provider_smoke 10 | Provider smoke run 45505263658: one synthetic keyless remote call (`baidu/ernie-5.5-flash-preview:free`) | IMPLEMENTED+EXERCISED (single synthetic call) |
| Independent agents / registry | `blind_sniper_runtime.py`, `chatgpt-home/runtime/agents.json` | runtime planner CLI; agent_runtime | orchestration 28, runtime 3, tool_runtime 13 | none live; registry validated by CI runtime workflow | FIXTURE-ONLY / PARTIAL: registry and dispatch exist; no multi-agent run observed |
| Durable queue/lease/recovery | `blind_sniper_worker.py`, `_queue_schemas.py` | daemon | worker 20, queue_schemas 20, worker_workflow 6 | worker workflow exists; no resident worker observed | FIXTURE-ONLY |
| Ledger (hash chain, GitHub store) | `blind_sniper_ledger.py` | worker, executor, browser_dispatch | ledger 21, github_ledger 25 | no private-repo round trip observed | FIXTURE-ONLY (fake GitHub API). Source holds a local `TaskLedger`, a `GitHubContentsLedger` compare-and-swap adapter and a `GitHubPrivateObjectStore`; their existence is source-verified. A live private-repository round trip and cross-run recovery are NOT verified. Do not read this as an operational GitHub-backed ledger. |
| Executor | `blind_sniper_executor.py` | CI workflows | executor 14, executor_workflow 12, receipt 12 | executor workflows exist; run history not re-read here | IMPLEMENTED, CI-exercised per audit; UNKNOWN for current runs |
| Patch verify | `blind_sniper_forge_verify.py` | executor `forge-patch-verify` | forge_verify 6 | no run seen | FIXTURE-ONLY |
| Tool runtime | `blind_sniper_tool_runtime.py` | daemon -> agent_runtime | tool_runtime 13 | none live | FIXTURE-ONLY. The tool runtime also exposes `repo.write_file` behind task allowlists and permissions, so it is not read-only; tests proving path confinement, task authorization and no writes outside a fixture workspace are still required. |
| Native browser | `blind_sniper_browser.py`, `_browser_dispatch.py`, `_mcp_server.py` | browser workflow, MCP stdio | browser 44, dispatch 9, mcp 17 | browser workflow runs per audit (real Chromium on CI against fixtures/one read-only live site smoke script exists) | IMPLEMENTED+EXERCISED on CI for fixtures; session persistence on a resident host UNKNOWN |
| Memory/private persistence | `blind_sniper_memory*.py`, `_handoff*` | daemon capture; handoff runtime | memory 13, handoff 7, knowledge 4, retrieval 3, runtime 2 | memory workflow on PR | FIXTURE-ONLY; `memory_retrieval` has no production importer |
| Autonomy | `blind_sniper_autonomy.py` | none wired | autonomy 6 | refuses unattended mode by design | PARTIAL / UNWIRED to daemon |
| Watcher | `blind_sniper_watcher.py` | none wired | watcher 4 | none | PARTIAL / UNWIRED |
| Connectors/OAuth/token refresh | none in code | none | none | none | ABSENT (a local unpushed registry branch exists, fake HTTP only) |
| Notifications | daemon writes an events file; no sender | none | covered inside daemon tests | none | ABSENT for delivery |
| Deployment/runtime availability | `api/health.py`, `vercel.json` | HTTP GET | vercel_health 4 | health returns 200, `task_execution_enabled=false`, `worker=not_activated` | health only; task execution ABSENT in deployment |
| REE | `.github/workflows/ree-wrapper-run.yml` | manual dispatch | none | runs 45596006799 fail, 45607329745 fail, 45608107720 success (artifact files unread) | external wrapper, not native |
| Local small-model proof | local diffs outside repo | n/a | 46 on a fresh clone plus patch (local) | one local run, 6 of 7 mutants killed | LOCAL ONLY, not in `main` |
| Local fixture slice (not in this PR) | local scratch clone, unpublished | scripted provider through the real queue, worker and tool paths | local only | scripted-provider fixture tests exercise plumbing only. Local review found a defect where a task could be recorded as passing after a failed tool step; a fix exists locally, still has failing tests, and is held, not published. | LOCAL ONLY. Not a live-agent result. |
| Browser/other smokes | `scripts/run_blind_sniper_*_smoke.py` | workflows | daemon_once_smoke 2 | daemon-once run 45587990290 (stub model) | stub/fixture |

## Limits
- Test counts in the table are `def test_` counts, not pass/fail results. CI evidence, read from GitHub Actions job logs (signed-in log view) on 2026-11-26: PR head `78405036796a9a4591f2ef151f5999256b18e45d`. CI ran on the pull-request merge commit `b7ba53016268e6a103588a721983232d0ce231fe` (PR head merged into base `f9cde15`). Runtime Registry run `45818176838`, job `139903208416`, Python 3.12.16: `Ran 387 tests in 6.944s`, `OK`. Environment Validation run `45818176806`, job `139903207975`, Python 3.13.18: success. OS Compliance run `45818176675`, job `139903273616`: success, interpreter not recorded here. The Runtime Registry log contains interruption/recovery and scheduled-job simulation receipts with `actual_agent_spawned=false`, `execution_mode=SIMULATION_ONLY`, `external_network_calls=0`, `real_scheduler_present=false` and `scheduler_kind=deterministic_test_harness_not_a_real_scheduler`. These are CI and deterministic-harness evidence only, not a live agent, a real scheduler, a live model or production task execution. No run on Python 3.11 is claimed. The earlier audit #79 baseline was 376 tests with 3 environmental errors on Python 3.10.12.
- "IMPLEMENTED+EXERCISED" here means a CI or sandbox run was reported, not that it is production-proven. No production task execution exists.
- Rows marked UNKNOWN need a fresh read of Actions run history for the workflows they name; only the three runs above were read.
- Workflow trigger details were counted by string match and should be re-read before use.
- Test method counts mix unit, fixture and simulation tests; the table does not separate them.

## BS-001 acceptance criteria mapping (assistant mapping for review, not an acceptance verdict)
Criteria are quoted from `docs/roadmap/ADVANCED_MASTER_BUILD_PLAN.md`, section "BS-001 - Final Architecture and Code Inventory", on the PR #80 branch. Status of the ticket: submitted, PENDING REVIEW.

| # | Criterion | Evidence | Status | Gap |
|---|---|---|---|---|
| 1 | Every listed runtime capability maps to source files, trigger path, tests and evidence status | The capability table above (Source, Trigger path, Tests, Live evidence, Status columns) | Mapped, static | Some rows PARTIAL or UNKNOWN. Test counts are method counts. Some modules were read by docstring and imports only (map section 7). |
| 2 | Every external dependency classified | `docs/architecture/CURRENT_RUNTIME_MAP.md` section 4; boundary conflicts in section 5 | Classified | Section 5 items are open for review. `chatgpt-home/` docs were not read for claims. |
| 3 | No unsupported production or autonomy claim in current-state docs | Dated notices at the top of `chatgpt-home/CURRENT_STATE.md` and `chatgpt-home/runtime/BUILD_PROGRESS.md` | PENDING REVIEW | Older entries were not rewritten and some are stale. |
| 4 | Inspection limitations and unverified deployment state explicit | Map section 7; the Limits section above; UNVERIFIED markers in `HOST_STORE_MODEL_DECISION_RECORD.md` | Stated | Deployment state beyond the health endpoint was not observed. |
| 5 | No application or runtime behavior changed | PR diff is 5 docs files: the two notices above, this matrix, the map and the decision record. Nothing under code, workflows or config. | Met per diff | None known. |

The plan also asks for a review against actual source paths and current GitHub state. That review is the reviewer's step and has not happened.
