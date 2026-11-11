# Independent Shadow Review — Issue #46 (P0 Autonomous Agent Runtime)

**Review mode:** READ-ONLY. No code changed, no commits to the implementation branch, no secrets, no live/paid API calls.
**Reviewer:** OpenHands (AI agent), fresh context, independent of the implementer session.
**Request:** issue #46 comment `6765624182`.
**Reviewed revision:** `feat/p0-autonomous-agent-runtime` @ `ce3c650fa5601889efb4642b51dd961b27332bf8` (base `main` @ `bed0df1664be72b060512eea218f7071f9bfa09c`).
**Receipt date:** 2026-11-10.

**Honest independence limit.** This is a *separate execution context* review, not a second human
account. The repository has a single collaborator; a distinct human sign-off remains a stronger
guarantee. A review is independent only when performed by a distinct reviewer identity/context from
the implementer — this satisfies the context-distinctness condition of `chatgpt-home/agents/shadow.md`.

---

## 0. Verdict

**BLOCKED** — the reviewed branch is red and R1/R2/R5 are unimplemented, so it must not be merged or
presented as a completed P0. The review also finds a **requirement-level contradiction**: the branch
deliberately *removes* R3 (OpenHands Cloud V1) and R4 (Forge MCP) as out-of-scope, while issue #46
still requires them.

One-line status of each requirement (details in §3):

| Req | Claimed by branch | Independent finding |
|---|---|---|
| R1 Independent model agents | not implemented | **NOT IMPLEMENTED** (role contracts only) |
| R2 Durable worker | partial | **PARTIAL** (local lease/CAS exists; no heartbeat/cancel/supervisor; cross-run unwired) |
| R3 OpenHands Cloud V1 adapter | removed as out-of-scope | **ABSENT** (scope contradiction) |
| R4 Forge MCP adapter | removed as out-of-scope | **ABSENT** (scope contradiction) |
| R5 Continuous autonomy | pending | **NOT IMPLEMENTED** (no trigger/schedule) |

---

## 1. What was inspected (evidence base)

- Branch diff `main..ce3c650`: 8 files, +247/−203 (`chatgpt-home/AUTONOMY_PROTOCOL.md`,
  `chatgpt-home/BLIND_SNIPER.md`, `chatgpt-home/BLIND_SNIPER_OS.md`, `chatgpt-home/runtime/BUILD_PROGRESS.md`,
  `chatgpt-home/runtime/README.md`, `chatgpt-home/runtime/capabilities.json`,
  `chatgpt-home/runtime/workflows.json`, `tests/test_blind_sniper_runtime.py`). [V]
- Main-branch runtime: `scripts/blind_sniper_runtime.py` (825 lines), `scripts/blind_sniper_ledger.py` (825),
  `scripts/blind_sniper_executor.py` (337), `scripts/blind_sniper_browser.py` (413),
  `scripts/blind_sniper_browser_dispatch.py` (152), `scripts/blind_sniper_receipt.py` (148). [V]
- Workflows: `.github/workflows/blind-sniper-{runtime,executor,browser,allowlisted-executor,environment-validation}.yml`,
  `engineering-execution-os-compliance.yml`. [V]
- Registries: `chatgpt-home/runtime/{workflows,capabilities,agents,profiles,authority}.json`. [V]
- Live GitHub: repo metadata, branch list, workflow runs, issue #46 and its 6 comments. [V]
- Official docs: OpenHands Cloud API and OpenAPI spec, MCP Streamable HTTP transport spec, GitHub Actions
  billing/events docs (§6). [V]

**Reproduction of the branch state (independent, in a clean worktree at `ce3c650`):**

```
$ python3 scripts/validate_blind_sniper_runtime.py
FAIL: 1 runtime registry error(s)
- orphaned workflow contract file: chatgpt-home/workflows/agent-handoff.md
VALIDATOR EXIT=1

$ python3 -m unittest discover -s tests -p 'test_*.py'
Ran 158 tests in 2.425s
FAILED (failures=5, errors=4)
TEST EXIT=1
```

Failing tests: `test_blind_sniper_orchestration.py::{test_engineering_task_routes_through_registered_profile,
test_high_risk_action_requires_owner_approval, test_task_envelope_cannot_self_approve_high_risk_action,
test_closure_requires_correlated_independent_reviewer_receipt, test_owner_approval_requires_action_verbatim_words_and_timestamp,
test_standing_delegation_auto_approves_only_allowlisted_actions_for_exact_repo, test_unregistered_browser_adapter_blocks_execution}`
and `test_blind_sniper_runtime.py::{test_expected_capability_boundaries_are_explicit, test_validator_passes_on_repository_state}`. [V]

CI corroboration: `Blind Sniper Runtime Registry` run `42804757893` on the branch → **failure**; the
failing step is *Validate runtime registries* (step 4), which skips steps 5–8. `actions/runs?event=schedule`
→ `total_count: 0`. [V]

---

## 2. Prioritized threat / risk register

Severity: **BLOCKER** (must fix before merge) · **HIGH** · **MEDIUM** · **LOW**.

| ID | Sev | Finding | Evidence (file/line) |
|---|---|---|---|
| **R-01** | BLOCKER | Branch is red: validator fails on an orphaned workflow contract, and 9 tests fail. Merging would break `main` CI. | `scripts/validate_blind_sniper_runtime.py:221`; branch run `42804757893`; reproduced locally (§1) |
| **R-02** | BLOCKER | R1 is not implemented. `native_model_runtime` is registered as `not_implemented_pending_p0`; the runtime only *selects role contracts* and never invokes a model. There is no model client, no agent-run identity, no tool/permission allowlist enforcement, no bounded concurrency/retries. | `chatgpt-home/runtime/capabilities.json` (new `native_model_runtime` adapter, status `not_implemented_pending_p0`); `scripts/blind_sniper_runtime.py:218-388` `build_plan` sets `contract_loaded_by_host: False` |
| **R-03** | BLOCKER | Scope contradiction with issue #46: the branch *deletes* the `forge_browser_mcp` and `openhands_dispatch` adapters and *removes* the `openhands-two-way-handoff` and `forge-browser-roundtrip` workflows, and the docs declare OpenHands/Forge "out of scope". Issue #46 R3 and R4 still require these adapters. Either the issue must be amended by the Owner, or R3/R4 must be restored. | `chatgpt-home/runtime/capabilities.json` diff (removed adapters); `chatgpt-home/runtime/workflows.json` diff (workflow ids replaced); `chatgpt-home/BLIND_SNIPER_OS.md` diff ("External agent runtimes and external browser agents are out of scope") |
| **R-04** | HIGH | R2 durable worker is incomplete: there is **no heartbeat** event type, **no cancellation** command, **no stale-lease supervisor/reaper**, and **no cross-run reconciliation worker**. `EXECUTION_ENGINE.md` itself states the adapter "does not implement cancellation or stale-worker recovery scheduling". | `scripts/blind_sniper_ledger.py` (`_active_lease`, `claim_task`, `release_task` only); `chatgpt-home/runtime/EXECUTION_ENGINE.md` (cancellation/recovery disclaimer) |
| **R-05** | HIGH | The durable cross-run ledger is **not wired into any workflow**. `.github/workflows/blind-sniper-allowlisted-executor.yml` runs `blind_sniper_executor.py` **without** `--github-ledger`, so `cross_run_exclusion`/`cross_run_deduplication` are `False` and the "durable worker" is, in practice, per-run local state. The executor's own test asserts the *absence* of cross-run dedupe. | `.github/workflows/blind-sniper-allowlisted-executor.yml` (executor invocation, no `--github-ledger`); `scripts/blind_sniper_executor.py:108-110,154`; `tests/test_blind_sniper_executor.py:151` `test_reused_task_id_in_a_later_run_is_not_claimed_as_cross_run_deduplicated` |
| **R-06** | HIGH | Privacy: R2 requires private task payloads to stay out of this public repo. This repo **is public** (`GET /repos/...` → `private:false, visibility:"public"`). The design relies on the GitHub-contents ledger refusing public targets, but that guarantee is (a) not enabled in CI (R-05) and (b) **undocumented**; a future operator who sets `--github-ledger` against this repo gets a fail-closed error only at runtime. Also, the allowlisted-executor `publish-receipt` job writes receipts to a `receipts/main` branch — if wired to a task id derived from private work, that is a public leak path. | repo metadata `private:false`; `scripts/blind_sniper_ledger.py:505-515` `_assert_private_repository`; `.github/workflows/blind-sniper-executor.yml` `publish-receipt` job |
| **R-07** | HIGH | The branch removes the only working cross-repo handoff route without replacing it, and marks the replacement `not_implemented_pending_p0`. Net effect: autonomy *decreases*. The docs assert capabilities ("native browser CI e2e passed") that are true for CI but not for an unattended host. | `chatgpt-home/runtime/workflows.json` diff; `chatgpt-home/runtime/BUILD_PROGRESS.md` diff ("independent model-process invocation remains unimplemented") |
| **R-08** | MEDIUM | R5 has no trigger: no `schedule:`/`cron:` exists in any workflow (`actions/runs?event=schedule` → 0). "Continuous autonomy" therefore cannot be demonstrated from the branch as-is. Correctly *not* activated — but also *not* designed into a workflow. | `.github/workflows/*` (no `schedule:`); `actions/runs?event=schedule` = 0 |
| **R-09** | MEDIUM | Browser write gating is a **host env-var attestation**, not cryptographic identity. `BLIND_SNIPER_BROWSER_WRITE_APPROVED=1` + any non-empty `--approval-reference` unlocks mutating actions. On a shared self-hosted runner an env var is weaker than a signed approval. This is acceptable only if documented as attestation, not proof. | `scripts/blind_sniper_browser.py:173-177` `_assert_write_approved` |
| **R-10** | MEDIUM | The hash chain detects edits but is **not signed** and not tamper-proof against a writer with repo write access; the branch does not add signing or an external witness. Treat as integrity-check, not audit-proof. | `scripts/blind_sniper_ledger.py` `_digest`/`_read_unlocked`; `EXECUTION_ENGINE.md` (explicit disclaimer) |
| **R-11** | MEDIUM | Idempotency is enforced only against **existing ledger rows**. In the local-ledger mode (default in CI) the ledger is discarded each run, so a repeated `task_id` is not deduplicated (see R-05). Any design that claims idempotency must state the storage scope. | `scripts/blind_sniper_ledger.py:125-129`; `scripts/blind_sniper_executor.py:154-155` |
| **R-12** | LOW | `GitHubContentsLedger` re-writes the **entire** ledger blob on every append (O(n²) commits, ~1 commit/event, 512 KB cap). Fine for control-plane state; will not scale to a real queue. Bounded and documented, but worth an explicit ceiling. | `scripts/blind_sniper_ledger.py` `_write_remote_content`, `MAX_LEDGER_BYTES=512*1024` |
| **R-13** | LOW | Leases are 1–3600 s and renewal is manual (`claim` per step). There is no automatic keep-alive, so a long step can outlive its lease; the browser path compensates with a pre-action margin, the executor path does not. | `scripts/blind_sniper_ledger.py` `claim_task` bound; `scripts/blind_sniper_browser_dispatch.py` margin check |
| **R-14** | LOW | The `CANCELLED` state is reachable by transition but **no command cancels** a task, and `EXECUTING`/`VERIFYING` cannot move to `CANCELLED` (only `BLOCKED`/`FAILED`/`OWNER-DECISION`). Cancellation semantics are inconsistent with the state machine. | `scripts/blind_sniper_runtime.py:67-75` `TRANSITIONS` |

---

## 3. Requirement-by-requirement assessment

### R1 — Separate model agents → NOT IMPLEMENTED (BLOCKER)
The runtime resolves *which* agent contract applies (`selected_agents`, `contract_loaded_by_host: False`)
and never invokes a model. `chatgpt-home/runtime/capabilities.json` adds a `native_model_runtime` adapter
whose status is literally `not_implemented_pending_p0`, and `BUILD_PROGRESS.md` states "independent
model-process invocation remains unimplemented". There are **no** files for a model client, agent-run
identity, fresh-context construction, tool/permission allowlist enforcement, concurrency bounds, retries,
or correlated run receipts. This is exactly the "agent contracts alone do not count" case the issue calls out.

### R2 — Persistent worker → PARTIAL (HIGH gaps)
What exists and is real: append-only hash-chained JSONL ledger (`blind_sniper_ledger.py`), `claim/renew/release`
with 1–3600 s leases, `flock` local atomicity, GitHub Contents SHA compare-and-swap for a **private**
target, server-`Date`-based expiry (fails closed without the header), and lease-gated browser reservation
with replay prevention. What is missing for R2: heartbeat, cancellation, stale-lease supervisor/reaper,
a reconciliation worker that survives independent runs, and any workflow wiring of the durable ledger (R-05).
The design is honest about this in `EXECUTION_ENGINE.md`, which is the correct posture.

### R3 — OpenHands Cloud V1 adapter → ABSENT (scope contradiction)
Issue #46 R3 requires the documented V1 adapter (create conversation, poll start task, status/messages/artifacts,
cancellation) with `OPENHANDS_CLOUD_API_KEY` bearer auth, redaction, idempotency and contract tests.
The branch instead **removes** the `openhands_dispatch` adapter and the handoff workflow and declares
OpenHands out of scope. No adapter exists. This directly conflicts with the issue.

### R4 — Forge MCP adapter → ABSENT (scope contradiction)
Same as R3: the `forge_browser_mcp` adapter and `forge-browser-roundtrip` workflow are removed. No Streamable
HTTP MCP client (`initialize`/`tools/list`/`tools/call`) exists. Issue #46 R4 still requires it.

### R5 — Continuous autonomy → NOT IMPLEMENTED
No `schedule:`/`cron:` trigger exists; no queue-polling loop; no stale-lease recovery; no health/digest
receipts. The branch adds registry entries for `native_task_queue` but no trigger. The issue's own gate —
"do not activate a schedule unless the executor, data store and secret prerequisites are genuinely
configured" — is respected (nothing was activated), but the capability is not delivered.

---

## 4. Design changes the implementer should make (ordered)

1. **Fix the red branch first (R-01).** Restore or update `chatgpt-home/workflows/agent-handoff.md` so the
   validator's orphan check passes, and update `tests/test_blind_sniper_orchestration.py` (it still requests
   the removed `forge-browser-roundtrip` workflow and asserts `PARTIAL` readiness that is now `BLOCKED`).
   A red branch cannot be reviewed as "done".
2. **Resolve the R3/R4 scope contradiction before writing more code (R-03).** Either (a) get the Owner to
   formally amend issue #46 to a self-contained-only architecture, or (b) keep the adapters (disabled by
   default, mock-tested) as the issue requires. Do not silently delete required scope.
3. **Make the durable ledger actually durable in CI (R-05).** Wire `--github-ledger` (with a **private**
   target repo) into the executor workflow, or state plainly in the PR that the executor is per-run and R2
   is PARTIAL. Add a cross-run test that proves a second run *cannot* claim the same task id.
4. **Add the missing R2 primitives:** `TASK_HEARTBEAT` renewals, a `cancel` command with consistent
   transitions (allow `EXECUTING/VERIFYING → CANCELLED`), and a supervisor that reclaims expired leases and
   emits a reconciliation receipt. Each needs a deterministic test.
5. **Implement R1 behind a provider interface** with: unique `agent_run_id` + `task_id` correlation,
   fresh bounded context, an explicit per-agent tool/permission allowlist enforced *before* the call,
   concurrency cap, timeout, bounded retry, and a correlated run receipt. Mock the provider for contract
   tests; do not call a live paid API without Owner quota/cost confirmation.
6. **Document privacy boundaries where the code enforces them (R-06).** Put the public-repo refusal in the
   runtime README and in the executor workflow comment, and never point `--github-ledger` or the
   `receipts/main` publish path at this public repository.
7. **Label browser write approval honestly (R-09):** "host attestation, not cryptographic proof", and keep
   mutating actions gated by explicit host approval as R4 requires.

---

## 5. Falsifiable acceptance tests (each must FAIL on the current branch)

Write these as real tests; each has an unambiguous pass/fail.

- **A1 (R1):** Given a fake provider, `invoke_agent(task_id, agent_id, allowlist)` returns a receipt
  containing a unique `agent_run_id`, the `task_id`, the model id, and the enforced tool set; two calls
  produce **different** `agent_run_id`s. *Current: no such function → fail.*
- **A2 (R1):** A tool not in the agent allowlist raises before any provider call (assert the mock provider
  was never invoked). *Current: fail.*
- **A3 (R2):** Two independent processes (or two `GitHubContentsLedger` instances over a shared private
  fixture) racing `claim_task` on one task id: exactly one returns `claimed:true`; the loser sees the winner's
  `owner_id`. *Current: only local `flock` is exercised; cross-process/remote path has no test.*
- **A4 (R2):** A lease that expires is reclaimed: after `lease_expires_at`, a `recover`/supervisor step
  records a stale-lease receipt and the task becomes claimable again by a new owner. *Current: fail.*
- **A5 (R2):** `cancel` on an `EXECUTING` task records `CANCELLED` and blocks further step reservations.
  *Current: no `cancel`; `EXECUTING → CANCELLED` is not even in `TRANSITIONS` → fail.*
- **A6 (R2 privacy):** `GitHubContentsLedger` pointed at a repo whose metadata `private:false` raises
  `GitHubLedgerError` on read and write. *Passes today — keep it and add a regression test.*
- **A7 (R3):** With `OPENHANDS_CLOUD_API_KEY` unset, the adapter is **disabled** and raises a typed error;
  with a mocked HTTP transport it performs create → poll `start-tasks` until `READY` → fetch
  `app-conversations?ids=` → `conversation/{id}/events/search`, and redacts the bearer token from every
  logged line. *Current: no adapter → fail.*
- **A8 (R4):** A mocked Streamable HTTP MCP server: client sends `initialize`, receives an `Mcp-Session-Id`
  (assert it is echoed on later requests), calls `tools/list`, then `tools/call` for an allowlisted tool;
  a non-allowlisted tool name is rejected client-side before the call. *Current: no client → fail.*
- **A9 (R5):** A `schedule`-triggered workflow exists **and** a run with `event=schedule` is observed, OR the
  capability is reported BLOCKED. *Current: `event=schedule` count is 0 → must be reported BLOCKED, not "added".*
- **A10 (R5):** Health digest receipt is produced by the queue poller with counts (claimed/renewed/expired)
  and is redacted. *Current: fail.*

---

## 6. Official documentation citations

- **OpenHands Cloud V1 (R3).** `POST https://app.all-hands.dev/api/v1/app-conversations` (async start task),
  `GET /api/v1/app-conversations/start-tasks?ids=` (poll until `status:"READY"` and `app_conversation_id`),
  `GET /api/v1/app-conversations?ids=`, `GET /api/v1/conversation/{id}/events/search`,
  `DELETE /api/v1/app-conversations/{id}`, `POST /api/v1/sandboxes/{id}/pause|resume`.
  Docs: <https://docs.openhands.dev/openhands/usage/cloud/cloud-api>; machine spec:
  <https://docs.openhands.dev/openapi/openhands-cloud.json>.
  **Auth caveat to verify:** the OpenAPI spec's declared scheme is `APIKeyHeader` with header
  `X-Access-Token` (global `security` unset; per-operation `security:[{APIKeyHeader:[]}]`), while the docs
  and the OpenHands API skill use `Authorization: Bearer <OPENHANDS_CLOUD_API_KEY>`. Build the adapter to
  send the documented Bearer header and add a contract test that asserts the exact header; confirm against a
  live sandbox only after the Owner approves quota/cost. **Cancellation:** there is no dedicated
  "cancel conversation" path; the closest are `DELETE /api/v1/app-conversations/{id}` and
  `POST /api/v1/sandboxes/{id}/pause`. Do not claim a cancellation API exists until confirmed.
- **MCP Streamable HTTP (R4).** Client MUST POST JSON-RPC to the MCP endpoint with an `Accept` header
  listing both `application/json` and `text/event-stream`; the server MAY return an `Mcp-Session-Id` on the
  initialize response which the client MUST echo; clients SHOULD `DELETE` the endpoint to terminate a
  session. Security: servers MUST validate the `Origin` header (DNS-rebinding), SHOULD bind to localhost
  when local, SHOULD authenticate all connections. Docs:
  <https://modelcontextprotocol.io/specification/2025-03-26/basic/transports>.
- **GitHub Actions (R5).** Scheduled workflows run on the latest commit of the default branch; the shortest
  interval is every 5 minutes; schedule times are UTC (IANA timezone optional). Standard GitHub-hosted
  runners are **free for public repositories** and do not consume included minutes. Docs:
  <https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows>,
  <https://docs.github.com/en/billing/concepts/product-billing/github-actions>.
  **Implication:** for this public repo, a `schedule:` trigger on standard runners is zero-cost and does not
  require a card — so R5's "no card" constraint is satisfiable, provided the durable store is a **private**
  repo (R-06).

---

## 7. Answers to the six review questions (a–f)

- **(a) True independent model execution vs role labels.** Still labels. `native_model_runtime` is
  `not_implemented_pending_p0`; the runtime selects contracts and never invokes a model. Not met.
- **(b) Cross-run queue/lease/heartbeat/cancel/recovery correctness.** Lease claim/renew/release and CAS are
  real and well-tested locally; heartbeat, cancel, stale-lease reclamation and cross-run reconciliation are
  absent, and the durable path is not wired into CI. Partial.
- **(c) OpenHands Cloud V1 security and cost controls.** Adapter removed (scope contradiction). The correct
  posture (disabled without the secret, mock-tested, no live calls) is described in the issue but not built.
  When built, send the documented Bearer header, redact it everywhere, and gate live calls on Owner quota.
- **(d) Forge MCP transport/auth/tool allowlisting and the ChatGPT Free-plan limitation.** Adapter removed.
  The plan-gated ChatGPT custom connector is correctly treated as unavailable on Free; the server-to-server
  MCP adapter that *is* buildable was not built. Use the MCP spec requirements in §6.
- **(e) No-card/no-paid continuous trigger design.** Feasible and correctly *not* activated prematurely. For
  a public repo, `schedule:` on standard runners is free; the durable store must be private. R5 is unbuilt.
- **(f) Privacy risk of storing queue state in this public repo.** **Real and confirmed.** The repo is public;
  the GitHub-contents ledger already refuses public targets, but that protection is neither wired into CI nor
  documented, and the executor's `receipts/main` publish path is a latent leak route. Keep all queue state,
  leases and receipts in a **private** repository and never point the executor at this one.

---

## 8. Owner-only gates (not resolvable by the implementer)

- **Scope decision (R-03):** amend issue #46 to self-contained-only, or restore R3/R4. This is a product
  decision and is the single most important unblocker.
- **Secret (R3):** adding `OPENHANDS_CLOUD_API_KEY` as a GitHub Actions secret is Owner-only.
- **Cost/quota (R3):** a live OpenHands Cloud round trip may consume paid quota; requires Owner confirmation.
- **Private store (R2/R6):** creating/pointing at a private repository for durable queue state is Owner-only.

_Generated by OpenHands (AI agent) on behalf of the repository owner. Read-only review; no code, secrets, or
paid API calls were used._
