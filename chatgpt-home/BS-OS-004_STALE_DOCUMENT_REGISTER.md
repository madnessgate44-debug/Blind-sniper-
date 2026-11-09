# BS-OS-004 — Stale-Document and State Register

**Status:** Register created; reconciliation actions are listed and gated by the owner/independent review.
**Register date:** 2026-11-09
**Baseline:** `main` at `ac8a5eb5f7b3eaf02be73733c7f49e53106da69e` (the PR #17 merge commit).
**Repository:** `madnessgate44-debug/Blind-sniper-` (PUBLIC).
**Authority:** `AGENTS.md` → `ENGINEERING_EXECUTION_OS.md` v2.3 → `chatgpt-home/BLIND_SNIPER.md` → `chatgpt-home/BS-OS-002_CANONICAL_ARCHITECTURE.md` → this register.
**Scope:** identify documents and registry entries on `main` whose recorded state is stale relative to live GitHub state. This document **does not overwrite** historical records; it records the discrepancy and the reconciliation action with provenance.

## 1. Outcome

Provide one canonical inventory of stale state so that current-state documents can be reconciled without destroying provenance, and so that live GitHub state — not stale prose — is the source of truth until reconciliation lands.

## 2. Method

- Re-read live GitHub state (branch heads, PR records, workflow runs) via the connected GitHub integration on 2026-11-09.
- Compared each canonical document on `main` against that live state.
- Grading: **[V]** verified against live state; **[S]** stale (contradicted by live state); **[X]** cross-repository (out of this repository's scope; recorded only).

## 3. Document inventory

| # | Document (on `main`) | Recorded claim | Live state (2026-11-09) | Grade | Action |
|---|---|---|---|---|---|
| D1 | `chatgpt-home/CURRENT_STATE.md` line 6 | PR #17 "OPEN / READY FOR REVIEW / NOT MERGED" | PR #17 **merged** 2026-11-09T02:40:51Z; merge commit `ac8a5eb` | [S] | Reconcile: mark #17 merged; preserve the original line as a dated superseded note |
| D2 | `chatgpt-home/CURRENT_STATE.md` line 35 | "`main` does not yet contain the consolidated runtime" | `main` **is** the #17 merge commit `ac8a5eb` and contains the consolidated runtime | [S] | Reconcile as above |
| D3 | `chatgpt-home/CURRENT_STATE.md` line 36 | "PR #17 is ready for independent review" | #17 already merged | [S] | Reconcile as above |
| D4 | `chatgpt-home/CURRENT_STATE.md` line 44 | "then merge PR #17 and close superseded PRs" | next gate is now: merge #18 → #19; close #9/#13/#15/#16 as superseded | [S] | Reconcile next-gate text |
| D5 | `chatgpt-home/CURRENT_STATE.md` line 3 | snapshot "2026-11-09 02:31 UTC" | predates the 02:40:51Z merge | [S] | Update snapshot timestamp on reconciliation |
| D6 | `chatgpt-home/tasks/BS-20261108-002.md` line 5 | "VERIFIED — PR open, not merged" | its PR (#17) is merged | [S] | Add a dated status addendum; do not rewrite the historical status line |
| D7 | `chatgpt-home/tasks/BS-20261108-003.md` | (absent on `main`) | exists on PR #9; extracted to `main` by PR #21 | [S] | Landed via PR #21 |
| D8 | `chatgpt-home/CODEX_RUNTIME_ARCHITECTURE.md` | "Last reconciled 2026-11-08" | predates the #17 merge and the current PR set | [S] | Add a dated "last reconciled" bump; keep the historical date |
| D9 | `chatgpt-home/FOUNDATION_RECOVERY_PLAN.md` line 88 | "PR #147 observed OPEN / NOT MERGED" | cross-repository (Firstborn); not re-verified here | [X] | Leave; refresh only with cross-repo evidence |
| D10 | `chatgpt-home/OPENHANDS_WORKING_AGREEMENT.md` line 50 | Firstborn PR #147 status | cross-repository; not re-verified here | [X] | Leave |
| D11 | `chatgpt-home/PROJECTS.md` line 20 | Openhands `docs/STATUS.md` (2026-11-08) | cross-repository; explicitly flagged "refresh before relying" | [X] | Leave |

## 4. Registry and catalog drift (on `main`)

These are structural drift findings; PR #18 reconciles most of them. Recorded here so the register is complete.

| # | Area | Drift | Action |
|---|---|---|---|
| R1 | Agents | `agents.json` registers 10; `chatgpt-home/agents/` has 13 files. Unregistered: `factory-orchestrator`, `harness-controller`, `independent-reviewer`, `worker-executor` | Register as `reference_profiles` (`reference_only_not_in_native_roster`) — PR #18 |
| R2 | Agents | `blind-sniper` is registered with no matching agent file | Confirm intentional (root role) or add contract |
| R3 | Skills | `chatgpt-home/skills/github-research/` exists but is not in `skills.index.json.native_skills` (10 indexed) | Index it, or mark reference-only — PR #18 |
| R4 | Workflows | 4 workflow docs unreferenced by the registry: `isolated-execution-line`, `idea-to-contract`, `plugin-and-tool-onboarding`, `verification-and-handoff` | Register or mark reference-only — PR #18 |
| R5 | Workflows | 6 registry entries have no `native_contract_path` (`research-and-synthesis`, `forge-browser-roundtrip`, `persistent-browser-host-acceptance`, `continuous-autonomy`, `conversation-archive-export`, `native-browser-acceptance`) | Mark `contract_mode: registry_only` with reason — PR #18 |
| R6 | Agents | `release-manager` labelled `source: openhands-library` though it is in the canonical native roster | Relabel to native — PR #18 |

## 5. Provenance rule

- Historical status lines are **preserved**. Reconciliation adds a dated addendum (e.g. "superseded 2026-11-09: see …") rather than deleting the original claim.
- Live GitHub state is authoritative until the reconciliation PR lands on `main`.
- Cross-repository claims (D9–D11) are out of scope and are not modified without their own evidence.

## 6. Next actions

1. Reconcile `CURRENT_STATE.md` (D1–D5) and `BS-20261108-002.md` (D6) on the canonical line, preserving provenance.
2. Land PR #18 (R1, R3–R6) and PR #21 (D7).
3. Refresh `CODEX_RUNTIME_ARCHITECTURE.md`'s reconciliation date (D8).
4. Keep this register current; add a row whenever a live state change supersedes a document.

## 7. Addendum — 2026-11-09 (post-integration reconciliation)

Added when PR #22 was refreshed onto the reconciled integration stack. The original register above is preserved unchanged.

- The integration stack now carries the reconciled state on top of current `main` (`a33e38e`): PR #18 head `350e084`, PR #19 head `ab07de6`, PR #21 head `09bf032`.
- D1–D5 (`CURRENT_STATE.md`): the reconciled `CURRENT_STATE.md` no longer states PR #17 is open/unmerged; it records the #17 merge, the standing-delegation authority and the BS-OS-001A reconciliation, with the prior 02:31 UTC snapshot retained under "Historical record" for provenance.
- D6 (`BS-20261108-002.md`) and D8 (`CODEX_RUNTIME_ARCHITECTURE.md`): still open; tracked here, not yet edited.
- D7 (`BS-20261108-003.md`): landed via PR #21.
- R1, R3–R6 (registry drift): reconciled by PR #18 — non-roster agent files are reference-only, the skills index covers all native skills, every workflow carries an explicit `contract_mode`, and the workflow registry now holds 18 entries (the four previously-unreferenced docs plus #19's `bounded-verification`).
- D9–D11 (cross-repository): unchanged; out of scope without cross-repo evidence.
- These edits are DRAFT-PR content only. No merge to `main`, no deployment and no history rewrite occurred; merge remains an owner decision.

## 8. Addendum — 2026-11-09 (post-merge reconciliation of the integration batch)

Added after the batch `#18 → #19 → #21 → #22 → #25` merged onto `main` (`19f6e4c`). The original register and the §7 addendum are preserved unchanged.

- The batch is fully landed on `main`: #18 (`c7a50fd`), #19 (`287446f`), #21 (`972b8d6`), #22 (`bcc5495`), #25 (`19f6e4c`); #26 (`5f04aa1`) also merged. Superseded #9/#15/#16 were closed with their accepted content shipped via #21 and #19.
- Live registry counts on `main` are now `native_skills=14` and `workflows=18` (was 11/17 at the register baseline `ac8a5eb`).
- D1–D5 (`CURRENT_STATE.md`): reconciled again this pass — the snapshot anchor, "latest merged work", "latest verification" and "open PR inventory" sections now reflect `main` at `19f6e4c`, `native_skills=14`, `workflows=18`, and an empty open-PR set. Original claims preserved above the "Historical record" heading.
- D6 (`BS-20261108-002.md`) and D8 (`CODEX_RUNTIME_ARCHITECTURE.md`): still open; tracked here, not yet edited.
- D7 (`BS-20261108-003.md`): landed via PR #21.
- R1, R3–R6 (registry drift): reconciled by PR #18.
- This addendum is committed on a reconciliation branch only. No merge to `main`, no deployment and no history rewrite; merge remains an owner decision.
