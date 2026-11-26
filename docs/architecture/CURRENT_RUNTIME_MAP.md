# Blind Sniper current runtime map (BS-001)

**Status:** read-only inventory, docs only. No runtime behaviour changed.
**Base:** `main` at `f9cde15b20f9aaac6095eb45e727da0dbdee3104` (re-checked 2026-11-26 13:12 Cairo; unchanged since audit #79).
**Author:** the owner's assistant (Instinct). The code in this repository is Gemini/Antigravity authored per the owner's rule; this document contains no code.
**Method:** static reading plus import-graph analysis of `scripts/`, `api/`, `.github/workflows/`, tests. Nothing was executed for this map. Test counts below are `def test_` counts, not pass results. Pass results come from the baseline in Issue #79 (376 tests, 3 environmental errors on Python 3.10.12) and were not re-run in this ticket. Python 3.11 was not available.

## 1. What exists (22 core modules, 7,950 lines, plus 12 helper scripts)

| Layer | Module | Lines | Role (from source) |
|---|---|---|---|
| Ledger | `blind_sniper_ledger.py` | 1062 | Append-only, hash-chained task event ledger; GitHub Contents API backend (compare-and-swap) and an in-process `TaskLedger`. |
| Queue | `blind_sniper_worker.py` | 518 | Claim, lease, heartbeat, cancel, recovery, reconciliation over the ledger. |
| Queue | `blind_sniper_queue_schemas.py` | 280 | Per-object schemas for queue adapter. |
| Planner | `blind_sniper_runtime.py` | 824 | Registry-driven planner and guarded lifecycle; has a CLI `main`. Reads `chatgpt-home/runtime/*.json`. |
| Model boundary | `blind_sniper_model_worker.py` | 422 | `AgentSpec`, `ModelTask`, `ModelWorker`, `NativeModelInvoker`; OpenAI-compatible HTTP transport. |
| Agent dispatch | `blind_sniper_agent_runtime.py` | 260 | `dispatch_task`: one model-agent invocation on a queue task. |
| Tools | `blind_sniper_tool_runtime.py` | 523 | Task-scoped tool registry: `agent.handoff` and browser tools; write tools only if in the task allowlist. |
| Host daemon | `blind_sniper_daemon.py` | 651 | Private-host loop: reads task files, host tool/path allowlist, receipts, health, notifications file, memory journal capture. Has `main`. |
| Handoff | `blind_sniper_handoff_runtime.py` / `blind_sniper_memory_handoff.py` | 149 / 314 | Model-authored handoffs to native private task files; claim-once. |
| Executor | `blind_sniper_executor.py` | 339 | Fixed 3-command allowlist (`unit-tests`, `runtime-validator`, `forge-patch-verify`); 600 s timeout; CI-driven. |
| Browser | `blind_sniper_browser.py`, `_browser_dispatch.py`, `_mcp_server.py` | 702 / 179 / 445 | Adapter around pinned `agent-browser` CLI, lease-gated dispatch from the ledger, MCP stdio server. |
| Memory | `blind_sniper_memory.py`, `_memory_knowledge.py`, `_memory_retrieval.py` | 243 / 232 / 124 | Privacy-gated local observation journal, approval-gated knowledge proposals, lexical retrieval. |
| Control | `blind_sniper_autonomy.py`, `_watcher.py` | 184 / 144 | Bounded recovery/health pass; one-shot watcher pass. Neither loops. |
| Support | `_redact.py`, `_receipt.py`, `_forge_verify.py` | 53 / 148 / 154 | Redaction, receipt schema, patch-verify fixture adapter. |
| HTTP | `api/health.py` | small | Read-only Vercel health: `task_execution_enabled: false`, `worker: not_activated`. |

## 2. Real import/call graph (from `import` statements)
```
daemon -> agent_runtime, handoff_runtime, ledger, memory, model_worker, tool_runtime, worker
agent_runtime -> ledger, model_worker, redact, tool_runtime, worker
tool_runtime -> browser, memory_handoff, redact
handoff_runtime -> memory_handoff -> memory -> redact
browser_dispatch -> browser, ledger, runtime
mcp_server -> browser, browser_dispatch, ledger, runtime
executor -> ledger, runtime          (does NOT import daemon or model_worker)
autonomy -> ledger, worker           (does NOT import daemon)
worker -> ledger ; runtime -> ledger
browser, forge_verify, watcher, queue_schemas, receipt, redact, ledger, memory_retrieval: no sibling imports
```
Consequences (observed from imports): there are two separate execution paths. (a) Host path: daemon -> worker/ledger -> agent_runtime -> model_worker/tool_runtime. (b) CI path: workflow -> executor -> runtime/ledger with a fixed command list. The executor does not call the model path. The watcher and autonomy modules are not wired to the daemon loop. `memory_retrieval` is imported only by tests, not by production modules (not dead-proven; may be a library entry).

## 3. Entry points and triggers
- Daemon: `python scripts/blind_sniper_daemon.py` (has `main`; `deploy/blind-sniper-worker.service.example` is an example unit, not an installed service).
- Planner CLI: `python scripts/blind_sniper_runtime.py`.
- Executor: dispatched by workflows `blind-sniper-executor.yml` and `blind-sniper-allowlisted-executor.yml`.
- Workflows (11): runtime, environment-validation, memory, compliance run on pull request; browser runs on PR and dispatch; daemon-once-smoke, provider-smoke, executor, worker, allowlisted-executor and `ree-wrapper-run` are dispatch-triggered (counted from `workflow_dispatch`/`pull_request` strings; exact trigger blocks should be re-read before relying on them).
- Vercel: `api/health.py` only. No task-execution endpoint exists.

## 4. External runtime dependencies (classification)
| Dependency | Where | Class |
|---|---|---|
| OpenAI-compatible model provider endpoint | `model_worker`, provider smoke | inference-only (runtime when configured) |
| GitHub Contents/REST API | ledger, executor server-time, repo checks | runtime dependency of the GitHub-backed ledger; not forbidden by the plan, flag for owner |
| `agent-browser` CLI (pinned) + Chromium | `browser` | runtime dependency of the browser path, installed by CI or host |
| `reverse-engineer-everything` (pinned `ab07274`, MIT) | `ree-wrapper-run.yml` | build/test-only, manual, cloned at CI time |
| Forge/Firstborn | `blind_sniper_forge_verify.py`, executor command `forge-patch-verify` | name/format only: reads a fixture patch inside the repo; no network, no Forge call |
| OpenHands mirror | `find_skill.py`, `adapt_skill.py`, `blind_sniper_runtime.py:214`, `validate_blind_sniper_runtime.py` | documentation/skill-catalog reference to `chatgpt-home/openhands-library/...` paths |
| Instinct | no script, workflow or api file references it | none found in code; docs only |
| `generativelanguage.googleapis.com/v1beta/openai` | default endpoint in `run_blind_sniper_provider_smoke.py:41` and `blind-sniper-provider-smoke.yml:11` | inference-only (Gemini OpenAI-compatible endpoint, overridable input) |
| `amina-nine-sepia.vercel.app` | default target of `run_blind_sniper_miss_noor_smoke.py:18`; `blind-sniper-browser.yml:85-87` sets it as the only allowed browser domain | test-only read-only live-site smoke against a separate owner product (Miss Noor); not a runtime dependency |

## 5. Standalone-boundary conflicts to review
1. `forge-patch-verify` and the `forge` docstring tie the executor vocabulary to Forge. Not a call, but BS-002 would likely rename or re-contract it.
2. Skill tooling points at an OpenHands mirror directory. Verified present on `main`: `chatgpt-home/openhands-library/` (contains AGENTS.md, BLIND_SNIPER_AUTHORITY_OVERLAY.md, IMPORT_MANIFEST.md and more). It is copied documentation/skills, not called at runtime by the scripts read; BS-002 should decide whether to keep it as docs.
3. The two hosts are resolved above (provider default endpoint; Miss Noor test target). Neither is an orchestration dependency.
4. Docs under `chatgpt-home/` mention Forge/OpenHands/Instinct widely. Not read for claims in this ticket.
5. GitHub is both ledger store and CI host, so "standalone" in the plan does not cover GitHub; the owner should confirm that is intended.

## 6. Not covered or limited
- Actions history: the 12 most recent runs (2026-11-25 to 2026-11-26) were read; all Engineering Execution OS Compliance runs on `f9cde15`, `1804a8f`, `4257e0f`, `fb2cfd0` succeeded, REE `45608107720` success. That is a doc-compliance workflow, not behavioural proof.
- Not executed, so no new pass/fail evidence. Python 3.11 rerun still not done.
- Not read line by line: `queue_schemas`, `memory_knowledge`, `memory_retrieval`, `handoff_runtime`, `memory_handoff`, `browser_dispatch` internals, `ops/oracle-free`. Their roles above come from module docstrings, imports and tests.
- Deployment state: only the Vercel health endpoint was observed (HTTP 200, execution disabled) earlier today in the audit. No resident worker was observed.
- `chatgpt-home/CURRENT_STATE.md` and `runtime/BUILD_PROGRESS.md` stop at 2026-11-17. This PR prepends a dated reconciliation notice to each (additions only, nothing deleted); the original dated entries are left as history, not rewritten.
