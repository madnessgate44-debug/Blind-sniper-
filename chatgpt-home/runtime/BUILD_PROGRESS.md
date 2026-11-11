# Blind Sniper build progress — current status

**Snapshot:** 2026-11-11 — PR #51 is latest merged implementation (`99b5efc`); PR #52 is open/draft at `896c044`, adding the native private-host worker daemon.
**Architecture:** Self-contained Blind Sniper. No external agent or browser handoff.
**Latest merged source PR head:** `e610c3a31418e10bc8498c574b8719ae72335355`. **Current daemon PR head:** `896c0441cb774b7b7bd94e6a8dbbef88f8c0855a`.
**Release:** NO-GO; this implementation merge is not a production deployment.

## P0 capability status

| Requirement | Current state | Evidence / remaining gate |
|---|---|---|
| R1 Independent model agents | IMPLEMENTED / LIVE-UNVERIFIED | Native HTTPS provider transport, fresh bounded context, distinct agent/run IDs, bounded retries and redacted receipts. Real provider round trip still needs approved private-host configuration. |
| R2 Durable worker and interruption recovery | PARTIAL | Digest-only dispatch, exact task-ID claim, heartbeat, expiry-checked completion/failure, bounded retry and stale-lease recovery. Private remote CAS cross-run persistence and private payload re-supply remain unverified. |
| R3 Native executor and tool runtime | IMPLEMENTED / HOST-UNVERIFIED | Bounded provider tool-call loop; `repo.read_file`, path-scoped `repo.write_file`, fixed `verification.run`; lease-bound receipts and replay refusal. Live provider-host execution remains unverified. |
| R4 Native browser | IMPLEMENTED / PERSISTENT-HOST-UNVERIFIED | Model-connected task-scoped Chromium tools; mutating browser actions require explicit host approval. Two local-fixture Chromium cycles passed; persistent browser host and cross-job recovery remain unverified. |
| R5 Continuous unattended autonomy | NOT IMPLEMENTED / BLOCKED | Native persistent worker/poller, private task payload retrieval and notification/health receiver remain to be built. No schedule is active. |

## Merged implementation

- `scripts/blind_sniper_model_worker.py`: native OpenAI-compatible provider transport plus bounded function-tool loop.
- `scripts/blind_sniper_tool_runtime.py`: static task-scoped repo, verification and browser tools; no arbitrary shell or unrestricted network.
- `scripts/blind_sniper_agent_runtime.py`: exact task-ID queue claim, lease propagation, model/tool invocation and completion/retry lifecycle; approval references are included in the task digest.
- `scripts/blind_sniper_worker.py`: atomic queue, exact-task claims, expiry-checked completion/failure, stale lease recovery and durable tool-call receipts.
- `scripts/blind_sniper_browser.py`: checked-in native Chromium adapter, invoked directly under queue lease; browser state/artifacts remain outside the public repo.
- Private task payloads and output receipts remain outside the public repository.

- `scripts/blind_sniper_daemon.py`: persistent single-host poller; owner-only task files, stale-lease recovery, native model/tool dispatch, private receipts, health and notification outbox. Privileges come only from host environment policy; task files cannot select tools or permissions. Native agent IDs are checked against `agents.json`.
- `scripts/blind_sniper_agent_runtime.py`: persists full private model receipts before queue terminal transitions; recovery reconciles only a receipt matching the current terminal queue attempt.
- `deploy/blind-sniper-worker.service.example`: hardened systemd template; not installed or started by CI.

## Exact-head verification ledger

| Action / workflow | Result | Evidence |
|---|---|---|
| Runtime Registry: registry validator + skill audit + Python unit suite + two E2E simulations | PASS | Run `42929073302`; 243 tests in 4.676s, `OK`; both simulations are SIMULATION_ONLY and report `actual_agent_spawned=false` |
| Environment Validation | PASS | Run `42929073606` |
| Engineering Execution OS Compliance | PASS | Run `42929073222` |
| Native Browser Adapter: Chromium local-fixture acceptance | PASS | Run `42929073319`; 2 cycles, 36 correlated receipts, interruption/no-replay/reconciliation |

- PR #52 head `896c044`; latest merged main commit remains `99b5efc` (PR #52 is not merged).
- No live model provider, private remote CAS cross-run, persistent browser host or unattended daemon was exercised. PR #52's daemon code is not active until an approved host provisions its private state directory and starts the systemd service.
- No paid provisioning, secrets/permission mutation, release or deployment.
- Next tranche: approved-host bootstrap and one bounded live provider/queue/browser acceptance cycle; then add a verified notification receiver and remote cross-host CAS/payload recovery. Do not enable unattended production autonomy until those gates pass.

---
## Historical build record

## Historical build record

## Historical build record

## Historical build record

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
- Private-repository gate + regression suite checkpoint: `165fdff5fde9c7e18fc3f30384ecfd44c2ef5705`.
- Local lease API and CLI checkpoints: `75f1ecc6cd94ca45f9581e867b9f9aa4583c622c`, `dba7c81f1e1bbc5b600d7a14cebc7f5f171d579e`.
- Atomic local execution transition checkpoint: `91a1ec8e0199cb6b833d5427d3bc8d9eb3471ed2`.
- Remote lease CAS and CLI integration checkpoint: `71c4aaaf7818c9327915d257f0ed126f3372d96c`, `61f4faf21ffe875bdaa72bb11f9ec226c4c01a70`.
- Atomic lease/snapshot validation and implementer binding checkpoint: `e78a7cb5a175ff1180826eed6e8985157573b74a`, `38f9e189305742cd872546546d8ff3ff26927335`.
- Terminal-task lease denial checkpoint: `f575191d22387c53935cd371da02689d486995c1`.
- Native-first boot/profile and legacy-plan supersession checkpoints: `672e64c741ec8a0cd998273a0cc7a163bbd63daa`, `9fc2b42c80f89a75b8b734fc26f33164b35db120`, `584a0be123784efb3ab5b9ea5ec45da856ad8faa`.
- Regression tests commit: `12a4a4149a163ed3c6870ba8ba543d06565cf1ae`.
- Runtime CI run [42484343595](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42484343595): SUCCESS; **29 tests passed**, including ledger-backed plan, transition, replay, stale-checkpoint recovery and host-forbidden denial.
- Latest runtime CI run [42484643917](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42484643917): SUCCESS; **31 tests passed**, including registry-owned routing, profile/agent selection, and the unprofiled browser workflow safely falling back to the default native profile/agents.
- Latest OS compliance run [42484643930](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42484643930): SUCCESS.
- Runtime CI run [42485004894](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42485004894): SUCCESS; **41 tests passed**, including six mocked GitHub Contents adapter tests, remote task-history recovery, CAS conflict retry and integrity failure.
- OS compliance run [42485004801](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42485004801): SUCCESS on the same test checkpoint.
- Runtime CI [run 42485134477](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42485134477): SUCCESS; **43 tests passed**, including refusal to access a public repository and remote task-history recovery.
- OS compliance [run 42485134395](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42485134395): SUCCESS.
- Runtime CI [run 42485831421](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42485831421): SUCCESS; **53 tests passed**, including local lease exclusivity, expiry reclaim, concurrent claim winner, atomic execution transition, remote lease CAS conflict retry and remote owner binding.
- OS compliance [run 42485831389](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42485831389): SUCCESS.
- Runtime CI [run 42486078702](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42486078702): SUCCESS; **54 tests passed**, including EXECUTING snapshot/task binding and implementer identity.
- Runtime CI [run 42486676603](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42486676603): SUCCESS; **55 tests passed**, adding terminal-task claim denial.
- OS compliance [run 42486078662](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42486078662): SUCCESS.
- Engineering Execution OS compliance run [42484343610](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42484343610): SUCCESS on test commit `12a4a41`.
- Documentation was updated after that runtime pass; latest HEAD and exact CI checks are maintained in `CURRENT_STATE.md`.

## Explicit limits

- The local ledger is workspace durable. An optional GitHub Contents API adapter is implemented and mock-tested, but no live write has been performed. It refuses public repositories by design.
- The checked-in GitHub Actions workflow has `contents: read`; it cannot write through the GitHub ledger adapter. No workflow permission was changed. A host must explicitly supply a token with Contents write permission and an authorized target branch.
- Lease expiry/reclaim is implemented, but there is no heartbeat scheduler, cancellation flow, stale-worker supervisor or background lease sweeper yet.
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


## Browser adapter tranche — 2026-11-08

R14 and R15 are verified on the native browser adapter. Run 42496827462 passed two consecutive real Chromium cycles through the native lease-gated dispatcher, exercising tabs, frame switching, approved upload, bounded download and PDF export. Each cycle recorded 18 started, 17 completed and one interrupted/reconciled action with 18 receipts; total 36 receipts.

Remaining:
- Oracle Always Free ARM64 host not provisioned; cross-job browser persistence not tested. Bootstrap and opt-in two-job test are in `ops/oracle-free/` and `scripts/run_blind_sniper_browser_persistence_probe.py`.
- Direct ChatGPT MCP connection unavailable on current Free plan; custom MCP app connections are web-only.
- Authenticated profiles/cookies intentionally unsupported.
- Independent full-diff review pending.
- PR #11 remains draft; no merge/deployment target is available.


## Owner architecture correction — 2026-11-10

- [V] Owner clarified that Blind Sniper is a self-contained system and must not depend on Forge or OpenHands for browsing, execution, delegation, persistence or recovery.
- [V] P0 issue #46 was rewritten to require native independent model agents, Blind Sniper-owned durable queue/worker recovery, native executor/tool runtime, native browser capability and safe continuous autonomy.
- [V] The native browser adapter already has CI-backed Chromium acceptance for bounded navigation/actions, task-lease checks, action receipts and interruption reconciliation. This does not prove a persistent authenticated browser host or cross-job browser-session recovery.
- [U] Independent model invocations are not implemented; the runtime currently resolves agent contracts rather than spawning separate model executions.
- [U] Full durable worker cancellation, heartbeat supervision, stale-lease reclamation and interruption-safe cross-run recovery remain incomplete.


## Native autonomy checkpoint — 2026-11-10

- [V] Branch `feat/p0-autonomous-agent-runtime` latest implementation commit at checkpoint: `1fad5f8de0316e8b5df7161fa9e53df64384858e` (21 ahead of main, 0 behind before this state-documentation commit).
- [V] PR #48 is a draft validation PR; it remains unmerged.
- [V] Runtime CI run `42805873386`: validator PASS; skill catalog audit PASS; 158 unit tests in 2.319s (`OK`); interruption/recovery simulation PASS; scheduled-jobs simulation PASS; artifact `13758272503`.
- [V] Environment validation `42805873383` and OS compliance `42805873397` both PASS on the same head.
- [V] The earlier E2E failure `42805773341` was caused by a simulation fixture selecting `task-control-loop`, which correctly fails closed because the native model provider is not configured. The fixture now selects `bounded-verification` for local deterministic work; the subsequent complete runtime workflow passed.
- [U] These checks verify the current planner, local ledger lifecycle and deterministic simulations; they do not verify independent model-agent invocation, a private cross-run queue worker, a persistent authenticated browser host, or unattended native autonomy.
- [U] R1 NOT IMPLEMENTED; R2 PARTIAL; R3 PARTIAL; R4 PARTIAL; R5 NOT VERIFIED.
