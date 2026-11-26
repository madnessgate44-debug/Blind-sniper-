# Decision record: host, store, free model path, and minimal threat model (draft)

**Status:** DRAFT for review. Docs only. Leads and constraints, not decisions and not promises. Nothing here was run or provisioned.
**Base:** `main` `f9cde15`. Written by the owner's assistant (Instinct). No code in this document. Any code that follows must be Gemini/Antigravity authored per the owner's standing rule.
**Constraint from the owner (recorded in `ops/oracle-free/README.md` and the owner's standing rules):** zero money, no card, no paid plan.

## 1. Host: what can run a worker for free

| Option | What the evidence says | Status |
|---|---|---|
| Vercel (today) | `api/health.py` reports `worker: not_activated`, `task_execution_enabled: false`. The plan's BS-007 says not to assume Vercel functions can host a resident browser. Function time limits were not checked here. | Health only. Resident worker not shown possible. |
| GitHub-hosted Actions runner | GitHub docs: standard runners are free and unlimited on public repositories; a job may run up to 6 hours; scheduled workflows can run at most once every 5 minutes. Sources: https://docs.github.com/en/actions/concepts/billing-and-usage, https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax, job-time figure from https://docs.github.com/en/actions/reference/limits (read through search excerpts; the page body did not load in my fetch). `daemon-once-smoke` (run `45587990290`, stub model) already runs the daemon once on such a runner. | Lead for a **bounded** worker (poll on a 5-minute schedule or on dispatch, work, exit). Not a resident worker. Private-repo minutes were not checked. Schedule reliability under load was not verified. |
| Self-hosted runner on a device the owner already has | GitHub docs: self-hosted jobs may run up to 5 days and are not billed. The repo has a systemd example (`deploy/blind-sniper-worker.service.example`). | Needs an always-on device and the owner's setup. Unproven. |
| Oracle Always Free | `ops/oracle-free/README.md` marks it **UNUSABLE**: signup needs a card. | Excluded on the owner's zero-money, no-card rule (stated by the owner in chat; the repo README only repeats it). An earlier note of mine listed it as a lead; that was wrong. |
| Others (free PaaS, notebooks, container hosts) | Not researched. | UNKNOWN. Do not assume. |

**Reading:** the plan's own definition of done (section 8) requires a persistent worker. On the evidence above, the only zero-cost lead that exists in code today is a **bounded, schedule-triggered worker on GitHub-hosted runners**, with all state kept outside the runner. Whether that meets "persistent" is a question for the owner and reviewer, not settled here.

## 2. Store
- Existing: GitHub Contents API ledger in a private repository (`blind_sniper_ledger.py`, hash chain, compare-and-swap, 512 KiB cap, private-repo check). Tested only against a fake API. A live private round trip has never been done (`CURRENT_STATE.md`, 2026-11-17).
- Token path (read from code and workflows): `blind-sniper-worker.yml` passes `secrets.BLIND_SNIPER_LEDGER_TOKEN` as `GITHUB_TOKEN` to the autonomy script, and `blind_sniper_ledger.py` refuses any repository that is not private (`_assert_private_repository`). This repository is public (GitHub API: `private: false`). The ephemeral per-run `GITHUB_TOKEN` is scoped to the running repository, so it would fail the private check here and cannot reach a different private repository. So the existing ledger path needs a separate private repository plus a token that can write to it, which does not exist in the workflows today. Not requested or created. Alternatives not yet evaluated: a different store, or keeping task state in public docs-safe receipts only.
- Existing zero-secret precedent: `blind-sniper-executor.yml` publishes receipts to a `receipts/main` branch with the per-run `GITHUB_TOKEN` (`contents: write`, one job only). Public by nature, so only for non-private fixture data.
- Plan BS-005 says GitHub Contents may not be treated as a production database without a justification. For one owner and a low task rate, the justification would be: single writer per run, CAS on every append, size cap. Not proven under concurrent runs. Flag for review.

## 3. Free model path
- One real call exists: provider smoke `45505263658`, keyless, model `baidu/ernie-5.5-flash-preview:free`, one synthetic prompt, `output_match true`. The endpoint URL is set by `BLIND_SNIPER_MODEL_BASE_URL`; The run's log lines I read do not show the host, logs need an authenticated token to download, and dispatch inputs are not exposed by the API. UNKNOWN. The `:free` suffix looks like a third-party aggregator naming style (inference only). Terms, privacy and zero-cost support of that endpoint are unverified; send it public fixture data only.
- Code default when no base URL is set: `https://generativelanguage.googleapis.com/v1beta/openai` (needs an API key, an owner action, and a free-tier quota check).
- Local small-model proof (Qwen2.5-0.5B via llama.cpp) proved plumbing and identity only, in a sandbox, not in the repo.
- Unknown: quality, rate limits and uptime of any free model for coding work. The seeded task in section 5 is how to find out.

## 4. Minimal threat model (proposed controls, none new are implemented)
Assets: the owner's repositories and tokens, the private ledger, model prompts.
Untrusted inputs: model output, task text, repository text, issue and PR comments, web pages.

| Risk | Control that exists today | Control the slice needs |
|---|---|---|
| Model output run as a command | Fixed command allowlist, no shell strings. `verification.run` allows `runtime-validator` and `unit-tests` (`blind_sniper_tool_runtime.py` lines 173-174). The executor map has the same two plus `forge-patch-verify` (executor lines 22-28; the third from the BS-001 audit) | Keep it. Model output is never executed; it may only fill an allowlisted file. |
| Writes outside scope | Executor is read-only. Daemon has host tool and path allowlists. `forge_verify` refuses paths outside the repo and applies to a temp copy. | Writes only to a fixture or branch copy. No push to `main`. No merge. A write tool is allowed only if it is in the task allowlist. |
| Secrets reaching the model or logs | `blind_sniper_redact.py`; credential-like payload refusal | Secrets only as Actions secrets. Not in prompts. Token scope limited to one private ledger repo. |
| Prompt injection from repo or issue text | None specific | Treat all such text as data. The agent's tool allowlist, not the prompt, limits actions. |
| Runaway cost or loops | Executor timeout 600 s; autonomy refuses unattended mode | Hard job timeout, max model calls per task, free endpoints only. |
| Browser misuse | Domain allowlist; write approval off by default; local-name refusals | Not needed for the first slice. Leave off. |
| Kill switch | Disabling the workflow or removing the secret | Document it. |

## 5. Minimal vertical slice (proposal)
- **Seeded task:** a small fixture repository inside the repo with one failing test. Agent roles: planner, builder, reviewer (three only).
- **What exists:** model boundary (`model_worker`), agent dispatch (`agent_runtime`), queue and ledger (`worker`, `ledger`), and the verify half (`forge_verify`: apply a diff in a temp copy and run fixed checks).
- **What the tool runtime offers (read from `blind_sniper_tool_runtime.py`):** `repo.read_file` (256 KB cap), `repo.write_file` (exact allowlisted paths, needs `workspace_write`, 128 KB cap), `verification.run` (fixed ids `runtime-validator`, `unit-tests`), `agent.handoff`, and `browser.*`. No search or patch tool. Whether a model-driven read, write, verify loop has ever run end to end is not shown by anything I read. That loop, on a fixture, is the slice.
- **Pass condition:** the builder edits only the allowlisted fixture file, the fixture test passes, the reviewer's verdict and all receipts are persisted, and the whole run is dispatched on a GitHub-hosted runner with a labelled live model call. Fixture-only or stubbed runs do not count.
- **Not part of it:** BS-002 rename work, browser, memory, notifications, UI.

## 6. Open questions for the owner and reviewer
1. Is a bounded schedule-triggered worker on GitHub-hosted runners acceptable for "persistent" at this stage?
2. May the owner provide a least-privilege ledger token (owner action) so a live private round trip can be tried?
3. Which free model endpoint should the seeded-task test use, and is a coding-quality bar of "fixture test passes" enough for the first gate?
