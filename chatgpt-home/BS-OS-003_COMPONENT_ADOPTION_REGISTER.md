# BS-OS-003 — Component Adoption Decision Register

**Status:** Decision register created; runtime adoption is gated by the evidence below.  
**Baseline:** `feat/bs-os-001a-registry-reconciliation-2026-11-09` at `26cdb69ade379422b375206491060b08ff946084` when this register was authored.  
**Authority:** `AGENTS.md`, `ENGINEERING_EXECUTION_OS.md` v2.2, `chatgpt-home/BLIND_SNIPER.md`, and `chatgpt-home/BS-OS-002_CANONICAL_ARCHITECTURE.md`.  
**Scope:** Decide which existing components should be retained, adopted, deferred or excluded. No executor code is changed here.

## 1. Outcome

Prevent duplicate framework implementation and identify the smallest viable path to a reliable native execution capability. The first implementation candidate is the existing allowlisted executor in PR #16, not a new executor.

**Decision:** Do not merge PR #16 yet. It has useful bounded-execution foundations and successful CI, but its current receipt does not represent the actual runtime lifecycle, and its durable-ledger claims are narrower than the architecture requires. The repository owner’s own inspection comment identifies those acceptance gaps, and there is no formal GitHub review submission. Keep the PR open and draft until repaired and independently reviewed.

## 2. Adoption decisions

| ID | Component | Decision | Reason | Required next evidence |
|---|---|---|---|---|
| A01 | Native Blind Sniper policy + registries + runtime state machine | **KEEP — canonical core** | Already the controlling architecture; avoid a competing imported OS | Maintain registry/OS compliance and lifecycle tests |
| A02 | Native append-only task ledger and lease primitives | **KEEP — canonical persistence core** | Existing hash-chain, lease, recovery and CAS abstractions are the native foundation | Continue corruption, replay, lease-expiry, recovery and private-target tests |
| A03 | PR #14 lease/approval hardening | **ADOPTED — merged into integration branch** | PR #14 is closed and merged at `431ff42040f7aa8f0bb21ea1515cf2bb20d34d0c`; its base is the orchestration integration branch, not main | Preserve its branch ancestry when reconciling the stack |
| A04 | PR #15 bounded ledger / compact snapshots | **CONDITIONAL — not merged** | 65 unit tests and validator reported successful on its head; branch is stacked on PR #14's branch; no formal review submission | Review diff and test artifacts; verify compatibility with PR #14; merge only after stack and target-base decision |
| A05 | PR #16 allowlisted executor | **DEFER — repair required** | Fixed command allowlist and read-only workflow are useful; exact head has successful registry, policy and environment CI. But executor receipt/lifecycle gaps remain | Correct lifecycle receipts, prove durable reservation semantics or narrow claims, test failure/retry paths, then independent review |
| A06 | PR #13 executor design contract | **KEEP AS DESIGN INPUT — not implementation** | It specifies a bounded executor with task/run/step-level reservations and correlated receipts; it is a separate draft PR | Reconcile its acceptance contract with the actual PR #16 implementation; do not let two documents drift |
| A07 | GitHub Actions bounded runner | **ADOPT AS OPTIONAL EPHEMERAL HOST** | Existing workflow can run two fixed read-only commands and upload artifacts; it is not a persistent daemon | Prove task-to-run correlation, lifecycle updates, artifact retrieval, retry/duplicate protection and explicit host limitations |
| A08 | OpenHands adapter | **DEFER — optional provider** | No proven direct dispatch/status/artifact/callback cycle in current host | One bounded, authorized, task-correlated end-to-end run |
| A09 | Forge/browser adapter | **DEFER — optional provider** | No callable Forge MCP in this session; native browser CI is not persistent authenticated browser hosting | Confirm actual callable tool and prove allowlisted browser task end-to-end without credential leakage |
| A10 | Ralph | **ADAPT SELECTED CONCEPTS ONLY** | PRD/task decomposition and progress memory are useful; full loop and permission defaults are not approved | Map any adopted concept to native task IDs, approvals, leases, receipts and stop conditions |
| A11 | Showcase/Mendelevium | **REFERENCE ONLY** | License evidence insufficient for verbatim copying; same source lineage | No code import until license/permission resolved |
| A12 | OpenHands mirrored skills and profiles | **REFERENCE ONLY** | Imported assets are not host-native executable agents | Explicit retrieval/adaptation and contract tests before activation |
| A13 | Private continuity / remote ledger repository | **BLOCKED** | No verified private storage target; current repo is public | A separately verified private destination and explicit authorization; do not place private content in public repo |
| A14 | Persistent autonomous worker / scheduler | **EXCLUDE FROM CURRENT CORE** | No verified persistent worker, reliable trigger receiver or cross-job continuity | Revisit only after a zero-cost host with correlated delivery and recovery is demonstrated |

## 3. PR #16 — exact review findings

### 3.1 Current repository facts

- PR #16 is open and draft.
- Head: `feat/allowlisted-executor-2026-11-09` at `7c3965bbfd3e2ccff44c59fc74ee7cd87f5b04ff` (updated 2026-11-09; was `025091c...`).
- Base: `fix/ledger-compact-bounds-2026-11-09` at `86c9b6277a00093b3d94a8baf065eacfd1a66a08`.
- It contains six changed files and twenty-two commits (updated 2026-11-09; was four files / seven commits).
- Its exact-head GitHub Actions runs concluded successfully (head `7c3965b`, re-verified 2026-11-09):
  - Runtime Registry: `42557468228`
  - Environment Validation: `42557468268`
  - Engineering Execution OS Compliance: `42557468229`
  - Allowlisted Executor: `42557462728` (artifact `13647678570`)
- The workflow job summaries report successful steps. They do not, by themselves, establish executor lifecycle correctness or independent review.
- GitHub reports `mergeable=true` / `mergeable_state=clean`; this is a Git mergeability signal, not acceptance.
- Formal review submissions: none.
- An owner-authored issue comment dated `2026-11-09T02:53:15Z` explicitly says this is an execution review finding, not independent approval, and asks to keep the PR open pending an independent task-correlated PASS.

### 3.2 Acceptance gaps

**G1 — Runtime lifecycle receipt mismatch (blocking).**  
The executor creates a runtime plan and advances task state through `INSPECTING`, `SPECIFIED`, `PLANNED`, `EXECUTING`, `VERIFYING` and `REVIEWING`, but its final embedded plan still reports all eight plan steps as `PENDING`. The command results are not reconciled into the plan's step-level status/evidence. A green command run therefore produces an internally inconsistent receipt.

**G2 — Reservation granularity and durability (blocking to the stronger PR #13 contract).**  
The executor claims a core task lease and writes a local `events.jsonl` artifact. That artifact is uploaded per run and is not a cross-run durable lease store. It does not implement task/run/step-level reservation and completion receipts as specified by the design input. Do not call this cross-run durable execution.

**G3 — Independent review absent (blocking to closure/merge).**  
No formal review submission exists. The owner comment expressly states that the prior inspection was not independent approval. A separate reviewer must inspect exact head and artifact, then provide a task-correlated PASS or actionable findings.

**G4 — Workflow trigger and operational boundary (acceptance scope).**  
The workflow is push-triggered for one named feature branch and a narrow path set. This is a useful controlled CI runner, not a generic task queue, scheduled worker or persistent executor. Preserve that description.

### 3.3 Repair and acceptance sequence

1. Update the executor's step records so each allowlisted command maps to a planned step with start/completion status, exit code, stdout/stderr references and commit/run correlation. All non-executed steps must remain explicitly pending or blocked with reasons.
2. Choose one honest persistence contract:
   - **Option A:** implement a verified shared/private durable reservation store with atomic cross-run lease and idempotency semantics; or
   - **Option B:** explicitly narrow the component to a per-run ephemeral CI executor, remove cross-run durability claims, and document that retry/duplicate protection is limited to the verified scope.
   Do not point a remote ledger at this public repository.
3. Test successful execution, first-command failure, second-command failure, timeout, duplicate run, task-ID reuse, artifact upload failure, missing/invalid server Date, and interrupted receipt finalization.
4. Ensure receipt state is derived from real command and step results, not from planned transitions alone.
5. Retrieve and inspect the exact artifact for the final head.
6. Obtain an independent review from a distinct reviewer identity; require a task-correlated PASS receipt.
7. Only then consider merging PR #16 into its intended base, preserving stack order. Any later promotion of the complete stack to main requires a separate diff/check review against main.

## 4. Stacked PR ancestry — do not flatten blindly

Current observed chain:

`PR #14 (merged)` → `PR #15 (open draft)` → `PR #16 (open draft)`

- PR #14 merged into `feat/blind-sniper-orchestration-integration-2026-11-08` at `431ff42040f7aa8f0bb21ea1515cf2bb20d34d0c`.
- PR #15 targets the PR #14 head branch and has head `86c9b6277a00093b3d94a8baf065eacfd1a66a08`.
- PR #16 targets PR #15's head branch and has head `7c3965bbfd3e2ccff44c59fc74ee7cd87f5b04ff` (updated 2026-11-09; was `025091c...`).
- PR #13 is a separate draft design PR targeting the orchestration integration branch; it is not in PR #15/#16's direct head-base chain.
- PR #9 is another draft E2E simulation branch; it reports a dirty merge state and is not a prerequisite for adopting the bounded executor.
- The architecture documentation branch in this repository is separate from that executor stack. Do not retarget or merge these branches merely to make the graph look linear.

## 5. Acceptance matrix

| Requirement | Acceptance criterion | Current result |
|---|---|---|
| R1 — Native-first authority | Native OS remains canonical; no wholesale external framework import | **PASS** — BS-OS-002 blueprint |
| R2 — Source eligibility | License/identity and adapter boundaries are recorded | **PASS** — source library and BS-OS-002 |
| R3 — Existing executor candidate inspected | Exact PR head, diff, CI, comments and formal reviews inspected | **PASS** |
| R4 — Executor lifecycle receipts correct | Step statuses reconcile to actual executed commands and evidence | **FAIL / BLOCKED** — G1 |
| R5 — Reservation semantics honest and adequate | Shared durable cross-run semantics proven, or scope explicitly narrowed | **FAIL / BLOCKED** — G2 |
| R6 — Independent review | Distinct reviewer provides task-correlated PASS on exact head/artifact | **NOT RUN** — no formal reviews |
| R7 — Stack integrity | Intended base and ancestry preserved; no accidental promotion to main | **PASS** — ancestry recorded; no stack changes |
| R8 — Safe adoption | Merge only after R4–R6 pass and branch checks remain green | **BLOCKED** |

## 6. Do not do

- Do not merge PR #16 in its current state.
- Do not describe its local per-run ledger as cross-run durable storage.
- Do not treat green CI, `mergeable=true`, an owner comment, or a profile label as independent approval.
- Do not create a second executor to bypass the gaps in PR #16.
- Do not write private data or remote ledger receipts to this public repository.
- Do not make OpenHands, Forge, private storage, or paid hosting a prerequisite for the native core.
- Do not promote a stacked branch to main without inspecting the complete cumulative diff and checks.

## 7. Next executable item

**BS-EXECUTION-001A — PR #16 Receipt Reconciliation**  
First fix G1 (planned-step to executed-step reconciliation) and choose Option A or B for G2. Keep the PR draft and open until independent review. This is a bounded repair of an existing implementation, not a new executor project.

---
**Decision:** Retain the native runtime and ledger. Treat GitHub Actions as an optional ephemeral executor. Repair PR #16's evidence model before adoption. Keep external providers and persistent autonomy deferred until a real end-to-end proof exists.
