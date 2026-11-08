# Blind Sniper build progress — 8 November 2026

**Architecture:** Native-first. Blind Sniper's own runtime, policy, workforce contracts, ledger and recovery are core. External agents are optional adapters.
**Integration branch:** `feat/blind-sniper-orchestration-integration-2026-11-08`
**Current state anchor:** `chatgpt-home/CURRENT_STATE.md`

## Completed

1. Native roster contains eight internal roles with checked-in contracts; external worker identities are not core roles.
2. Runtime policy prevents task envelopes from selecting profiles or overriding host-forbidden actions. Unknown/unclassified actions require action-specific approval; merge/default-branch/CI-CD actions are gated.
3. Closure requires PASS, reviewer distinct from implementer, matching task ID, full commit SHA and CI run ID. This is metadata validation, not cryptographic reviewer authentication.
4. Native append-only JSONL ledger provides sequence numbers, idempotency, process locking, fsync and SHA-256 chain validation.
5. Runtime `plan` now writes a `TASK_CREATED` snapshot to the ledger.
6. Every accepted `transition` writes a complete `TASK_TRANSITIONED` snapshot to the ledger before writing the convenience JSON checkpoint.
7. `recover` reconstructs the latest task state from the verified ledger.
8. Transition retries repair a stale checkpoint from ledger state; a repeated already-committed target does not append a duplicate transition.
9. Legacy task-state JSON can be adopted once as `TASK_IMPORTED`.
10. Host-forbidden actions are non-overridable; an Owner approval record cannot authorize force-push, branch deletion, credential/secret export, disabling branch protection or unbounded shell execution.
11. Optional `GitHubContentsLedger` adapter reads/writes the event file through GitHub Contents API, validates the full hash chain, uses blob-SHA compare-and-swap, retries conflicts and supports remote history/recovery reads.
12. Runtime CLI supports optional `--github-ledger` mode for plan, transition and recover; token is read only from a named environment variable.
13. Workflow routing priorities, keywords and per-workflow agent assignments live in `workflows.json`; profile binding comes from `profiles.json`. Duplicate runtime maps removed.

## Latest implementation evidence

- Runtime implementation commit: `cdad18b952b58dd3404fa66cee368724f5902627`.
- Host-forbidden policy commit: `d5e76f04533ce9ac9085cf471bf740966695fb3b`.
- Registry-owned routing commit: `56cdf4f54ab360c85f8ff547d21c8590273346be`.
- Runtime registry-driven selection commit: `a741f908f85184d4fe285205b61254aa95f91f58`.
- Safe fallback profile/agents correction: `eec6f124cba2612473f700290ea3dc273bf6f313`.
- GitHub Contents CAS adapter and runtime option: `156f6ba51a135986dfaf8f867391ac8b52e83b95`, `dcf38a1837be0cb620768f3bb0543e01d9f92218`, `f3527e88f174882db16d7d47aa491c92510f7449`.
- Remote adapter/recovery test checkpoint: `8a28e5076fd219f083a06ac04a3ece856aee6cac`.
- Regression tests commit: `12a4a4149a163ed3c6870ba8ba543d06565cf1ae`.
- Runtime CI run [42484343595](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42484343595): SUCCESS; **29 tests passed**, including ledger-backed plan, transition, replay, stale-checkpoint recovery and host-forbidden denial.
- Latest runtime CI run [42484643917](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42484643917): SUCCESS; **31 tests passed**, including registry-owned routing, profile/agent selection, and the unprofiled browser workflow safely falling back to the default native profile/agents.
- Latest OS compliance run [42484643930](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42484643930): SUCCESS.
- Runtime CI run [42485004894](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42485004894): SUCCESS; **41 tests passed**, including six mocked GitHub Contents adapter tests, remote task-history recovery, CAS conflict retry and integrity failure.
- OS compliance run [42485004801](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42485004801): SUCCESS on the same test checkpoint.
- Engineering Execution OS compliance run [42484343610](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42484343610): SUCCESS on test commit `12a4a41`.
- Documentation was updated after that runtime pass; latest HEAD and exact CI checks are maintained in `CURRENT_STATE.md`.

## Explicit limits

- The local ledger is workspace durable. An optional GitHub Contents API adapter is implemented and mock-tested, but no live write has been performed.
- The checked-in GitHub Actions workflow has `contents: read`; it cannot write through the GitHub ledger adapter. No workflow permission was changed. A host must explicitly supply a token with Contents write permission and an authorized target branch.
- The hash chain detects edits but is not a signed or tamper-proof audit log.
- Approval records are host-supplied attestations; the runtime cannot cryptographically prove who supplied the record.
- Reviewer identity is a distinct metadata field, not cryptographically authenticated.
- Native role contracts are not separately spawned model processes. The runtime is still a planner and guarded state engine, not an autonomous agent executor.
- No GitHub-backed compare-and-swap store, multi-host lease/claim queue, cancellation scheduler or full interrupted-run E2E has been implemented.
- Public-repository privacy containment remains unresolved; do not move or import private memory/transcripts into this public repository.
- No PR was merged; PRs #3, #6 and #7 remain open pending an explicit later consolidation decision.

## Next engineering sequence

1. Add GitHub-backed append-only persistence using immutable commits and optimistic concurrency, with no paid database.
2. Add task claims/leases, expiry, cancellation and stale-lease recovery.
3. Implement a bounded native executor adapter over only real host tools/CI runners; never represent contracts as spawned agents.
4. Bind executor receipts to task ID, step ID, exact commit SHA, workflow run ID and result artifact.
5. Exercise submit → execute → interrupt → recover → resume → verify → close.
6. Move routing ownership into registries and remove duplicated routing maps.
7. Reduce boot payload and measure actual bytes/lines before optimizing.
8. Reconcile branch graph and prepare a privacy-safe consolidated draft PR only after storage containment.
