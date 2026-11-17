# BS-AUTONOMY-002 — No-host event-driven runtime architecture

**Status:** CONDITIONAL ARCHITECTURE — bounded recovery and remote-clock safeguards are implemented and CI-verified; private state, live provider, notification delivery and autonomous activation remain blocked  
**Date:** 2026-11-15  
**Governing contract:** `ENGINEERING_EXECUTION_OS.md` v2.3  
**Scope:** `madnessgate44-debug/Blind-sniper-` only

## 1. Decision

Use GitHub Actions on the existing public Blind Sniper repository as a **bounded, ephemeral compute runner**. Use the already-existing owner-controlled private GitHub repository as the durable private control-plane store for task events, private task envelopes, model receipts, and agent handoff packets.

This is a conditional architecture decision, not an activation. [VERIFIED] GitHub repository metadata was read on 2026-11-17 and reports the existing owner repository `G` as `visibility=private`. Its identity is intentionally not repeated in this public ADR. [REPORTED] The active primary operating instructions record a five-file `blind-sniper-continuity/` scaffold in that private repository. [BLOCKED] The public Blind Sniper Actions runtime has no verified cross-repository credential, private payload/result adapter, or live model-provider configuration. The private repository exists; the missing item is the safe runtime access path, not repository creation.

No Forge or OpenHands service, API, session, browser, worker, issue route, or return path is part of this architecture.

## 2. Why this is the selected candidate

- [VERIFIED] The existing `GitHubContentsLedger` adapter already rejects any target repository whose metadata does not say `private: true`.
- [VERIFIED] It maintains a hash-chained append-only JSONL ledger, uses the Contents API blob SHA on update, retries bounded 409/422 conflicts, and requires GitHub's response Date header for remote lease time.
- [VERIFIED] The adapter's ledger file is capped at 512 KiB. It is a small control-plane event log, not a database or payload store.
- [VERIFIED] The existing public Blind Sniper repository reports `private: false`; it cannot be used for owner-private state.
- [VERIFIED] GitHub-hosted standard runners are free for public repositories and each run is an ephemeral VM/container. A worker must therefore persist all required state remotely before exit.
- [VERIFIED] An owner-controlled private GitHub repository already exists and its metadata confirms `visibility=private`; no duplicate repository should be created.
- [INFERENCE] Reusing that existing private repository is the only currently evidenced zero-incremental-cost persistent store that avoids an always-on host or payment-card signup. Runtime access still requires an explicitly configured narrowly scoped credential.

### Rejected alternatives

| Candidate | Decision | Reason |
|---|---|---|
| Public repository files, artifacts, caches, logs | REJECT | Public/private boundary violation; artifacts and caches are not the durable private ledger. |
| Local runner filesystem | REJECT | Each hosted run is ephemeral; no cross-run durability. |
| Vercel function local disk | REJECT | No durable shared filesystem or resident daemon. Existing Vercel adapter is health-only. |
| New external database/object store | DEFER | No already-connected, verified, no-card service is established. Adding one would introduce an unapproved external dependency. |
| Existing owner-private GitHub repository | SELECT CONDITIONALLY | Private visibility is verified; existing adapter supports private-repo checks and blob-SHA conditional updates. Cross-repository runtime access and payload/result persistence are not configured. |

## 3. Private data layout

The companion repository is the only location for owner-private runtime state:

```text
state/events.jsonl                 # hash-chained task/lease lifecycle events
payloads/<task-id>.json            # private task envelope; one bounded file per task
results/<task-id>/<attempt>.json   # private model/tool result and recovery receipt
handoffs/<handoff-id>.json         # private parent/child handoff packet
memory/                            # explicitly approved private durable memory only
```

The existing event ledger must contain only identifiers, lifecycle metadata, digests, lease ownership/timestamps, and safe error codes. It must not contain raw prompts, transcripts, task payloads, provider responses, credentials, or private handoff contents.

The payload/result adapter is **not implemented yet**. Each object must have a strict size limit, schema validation, idempotent create/update semantics, and blob-SHA conflict handling. Do not silently fall back to writing private payloads to the public repository.

## 4. Worker and concurrency model

1. A manual `workflow_dispatch` or best-effort scheduled trigger starts one bounded worker pass.
2. The worker checks that it is running from the trusted default branch and that all activation gates are satisfied.
3. The worker reads private task metadata and payloads using a repository-scoped credential.
4. It claims one task with a server-time lease and persists the claim before model invocation.
5. It invokes the native Blind Sniper model-agent runtime and allowlisted tool runtime. The model provider supplies inference only.
6. It persists model/tool receipts and handoff packets privately before marking the task terminal or spawning the next agent task.
7. On interruption, a later pass reconciles durable receipts, expires stale leases, and retries only within the task's explicit retry policy.
8. It emits only redacted metadata to public workflow logs and exits before the runner is destroyed.

### Concurrency rules

- Initially permit only one active writer for a given private queue/ledger.
- Keep blob-SHA compare-and-swap as a conflict detector; never treat a read followed by a write without SHA as atomic.
- Retain bounded CAS retries and fail closed on exhausted conflicts.
- GitHub Actions concurrency is a runner scheduling guard, not the durable queue. By default, a concurrency group keeps one running and one pending run; a new pending run can replace the previous pending run. Even with the extended queue option, the documented cap is finite and ordering is based on when runs enter the wait state. The private ledger remains authoritative; a later poll must rediscover pending tasks.
- Do not claim exactly-once model execution. Use at-least-once task recovery with idempotent tool receipts and explicit reconciliation; an interrupted external model request may have completed remotely without its response being persisted.

## 5. Platform limits and operational consequences

- Public-repository standard GitHub-hosted runner use is free and uses ephemeral machines.
- GitHub-hosted jobs have bounded execution time; the worker must checkpoint and exit rather than depend on a long-running process.
- Scheduled workflows are best effort: GitHub documents possible delays/dropped runs during load; they run only from the default branch; public-repository schedules can be disabled after 60 days without repository activity.
- GitHub Actions concurrency is not a database lock or durable task queue.
- GitHub Contents API updates require the current blob SHA. The API documentation warns that concurrent content operations can conflict. The implementation must handle conflicts and serialize writes where possible.
- Private repository storage/Actions allowances depend on the owner's GitHub plan. No workflow may spend beyond included free allowances; no paid usage or billing fallback is authorized.
- A private repository is access-controlled by GitHub, but this architecture does not add application-level encryption. Do not store secrets or data whose exposure would be unacceptable under the GitHub account's security boundary.

## 6. Credential boundary

Required owner-side setup, not performed by this task:

- Reuse the existing owner-private repository; do not create a duplicate. Confirm its default branch and the intended `blind-sniper-continuity/` data layout.
- Create a fine-grained personal access token restricted to that one repository.
- Grant only **Contents: read and write** (plus Metadata read as required by GitHub); no Actions, Administration, workflow, account, or organization permissions.
- Add it to the public repo as Actions secret `BLIND_SNIPER_PRIVATE_STATE_TOKEN`.
- Configure non-secret repository variables for the private repository owner/name/default branch.
- Configure the approved model-provider key separately as an Actions secret after selecting a provider and confirming its no-cost terms.
- Do not send token values in chat, issues, commits, or logs. Never attempt to read secret values through the connector.

The obsolete `OPENHANDS_CLOUD_API_KEY` reference has been removed from the native worker workflow; regression tests reject external-agent secret dependencies.

## 7. Activation gates

Production activation remains **NO-GO** until all are true:

- [x] Existing owner-private repository metadata confirms `visibility=private` (repository identity intentionally omitted from this public ADR).
- [ ] A narrowly scoped private-state credential is configured for the Blind Sniper workflow; secret values must never be read or printed.
- [ ] Runtime can read/write private task payloads, result receipts and handoff packets; public-repo refusal tests pass.
- [ ] Real GitHub API tests prove sequential writes, concurrent conflict/retry behavior, server-time lease expiry, idempotency and no lost events.
- [ ] Two separate hosted runs preserve state and do not double-claim a task.
- [ ] An injected interruption is reconciled by a later run without duplicate tool execution.
- [ ] Native model invocation is wired into the bounded worker and tested with a synthetic task.
- [ ] Two distinct native agents complete a handoff across separate runs.
- [ ] Synthetic privacy tests inspect logs/artifacts and prove no prompt, payload, transcript, provider output or handoff content leaks.
- [ ] Provider credential and terms are owner-approved; no paid model use or card-required route.
- [ ] Exact-PR-head CI passes; release-specific independent review and rollback criteria pass.
- [ ] Owner separately approves live production activation.

## 8. Current implementation blockers found during inspection

- [VERIFIED] `scripts/blind_sniper_autonomy.py::run_once` now recovers stale leases and emits aggregate-only health/digest artifacts without claiming pending tasks or consuming attempts. It is a recovery/health pass, not the native executor.
- [VERIFIED] `activation_check` keeps `executor_configured = False` and notification delivery false for this ephemeral Actions entrypoint; unattended execution remains intentionally blocked.
- [VERIFIED] `.github/workflows/blind-sniper-worker.yml` remains manual-only, has no schedule, and no longer references OpenHands or an external-agent secret.
- [VERIFIED] PR #62 merged the remote server-clock API, queue clock routing, five independent-process queue tests and four remote-clock regressions. Exact-head Runtime Registry run `43843357824` passed 330 tests; Memory Tests `43843357777` passed 63; Environment Validation `43843357804`, OS Compliance `43843357693`, and Browser Adapter `43843357688` passed.
- [UNVERIFIED] GitHub Contents API tests still use a fake transport for concurrency and remote clock behavior. Real private-repository CAS contention and cross-run payload/result recovery have not been proven.
- [VERIFIED] An owner-private repository exists (`visibility=private`); the primary operating instructions record its continuity scaffold. [BLOCKED] No verified cross-repository credential is configured for the public workflow, and no private payload/result adapter currently connects the runtime to that repository. The public repository is correctly rejected by the private-ledger adapter.
- [BLOCKED] Native model invocation and agent handoff code are present and contract-tested, but no approved live provider endpoint/key is configured or verified.
- [BLOCKED] No real notification delivery adapter/route or persistent approved worker host is configured.

## 9. Official platform references

- GitHub Actions billing and public-runner free usage: https://docs.github.com/en/actions/concepts/billing-and-usage
- Standard GitHub-hosted runners for public repositories: https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job
- Workflow concurrency and pending-run behavior: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- Scheduled workflow delays and public-repository inactivity behavior: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub Contents API create/update semantics and required blob SHA: https://docs.github.com/en/rest/repos/contents
- Fine-grained token permission requirements: https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens

## 10. Status

**Architecture:** CONDITIONAL; GitHub Actions are bounded ephemeral compute only; an existing owner-private repository is available as the candidate state store, but runtime access is not configured.  
**Code implementation:** PARTIAL; queue, remote-clock safeguards and fail-closed recovery are merged and CI-verified; private payload/result adapter and live integration remain incomplete.  
**Private-state integration:** NOT CONFIGURED.  
**Provider invocation:** NOT VERIFIED; no live provider is configured.  
**Scheduled polling:** NOT ENABLED.  
**Production deployment:** Health-only Vercel service is deployed after explicit owner authorization; `/api/health` returns HTTP 200.  
**Autonomous task execution:** NO-GO; worker remains not activated and task execution remains false.
