# Blind Sniper — connector and capability inventory

**Baseline:** `main` at `16920b5f21173b2fe8e90dfac0003ddbd8410304` (2026-11-27)  
**Scope:** Evidence-backed inventory of native tools, connector contracts, external integrations, and remaining enablement work.  
**Status rule:** code + tests = implemented in repository; authenticated live integration = operational. These are different states.

## 1. Current determination

Blind Sniper now has a native connector contract and process-isolated local connectors. It still does **not** have a fully operational external connector stack or a demonstrated autonomous software-company runtime.

- [V] PR #93 merged the connector contract/registry: discovery, tool schemas, role authorization, scope checks, cancellation contract, receipts, and unresolved-execution handling.
- [V] PR #103 merged native Files/Git connectors and a process runner with bounded output, scrubbed child environment, timeout/cancellation, process-group cleanup, and descendant cleanup tests.
- [V] The generic terminal connector exists in code but is **denied to runtime roles by default**. No broad `terminal.*` role grants remain. It is not an OS sandbox.
- [V] PR #104 merged CODEOWNERS, monthly GitHub Actions Dependabot configuration (PR-only), a PR evidence template, and SECURITY.md.
- [U] No authenticated external connector has been demonstrated end-to-end from the Blind Sniper runtime. A registry status of `verified` in a fixture is not live credential proof.
- [U] No continuous production daemon, persistent independent model-agent fleet, or unattended 24/7 execution has been demonstrated.

## 2. Native runtime and connector status

| Capability | Repository status | Evidence / limitation |
|---|---|---|
| Existing native repo tools | IMPLEMENTED | `scripts/blind_sniper_tool_runtime.py`; path jail, task allowlist, and approval checks in existing tests |
| Existing browser adapter | PARTIAL | `scripts/blind_sniper_browser.py` and MCP adapter; fixture coverage exists, but persistent authenticated browser session/recovery is not proven |
| Connector contract and registry | IMPLEMENTED (foundation) | `scripts/blind_sniper_connectors.py`; `tests/test_blind_sniper_connectors.py`; role/tool allowlist, scopes, schema validation, cancellation, receipts |
| Uncertain mutation handling | IMPLEMENTED (foundation) | Mutating call exceptions/timeouts and audit receipt failures become unresolved/UNKNOWN and block replay; operator reconciliation required |
| Native Files connector | IMPLEMENTED in repository | `scripts/blind_sniper_native_connectors.py`; dirfd traversal with no-follow parent traversal, atomic temp-file replacement, size caps; local temporary-directory tests |
| Native Git connector | IMPLEMENTED in repository | Read-only status/diff/log commands; local temporary-repository tests |
| Generic terminal connector | PRESENT, DISABLED BY DEFAULT | Exact executable path allowlist and process cleanup exist, but process isolation is not filesystem/network sandboxing. Runtime roles are denied `terminal.run_command`; do not enable without a separately reviewed sandbox/command policy |
| External GitHub read connector | PROPOSED / NOT MERGED | PR #96; public unauthenticated read only. Its live public GitHub test was disabled in the recorded CI run |
| Connector self-check | INCOMPLETE / NOT MERGED | PR #97; recorded CI marks Git/terminal blocked and live GitHub/authenticated integration unverified |
| Vercel, Google, Gmail, Drive, Calendar, Docs, Sheets, WhatsApp, Supabase, Render, Sentry, Notion, Figma | NOT OPERATIONAL | Specs/status labels or optional tool namespaces are not evidence of an authenticated native connector |

### Security boundary

- Process isolation is not an OS sandbox. The native runner does not claim to enforce filesystem namespaces, network egress policy, CPU quotas, or memory quotas.
- Terminal is not available to `engineer`, `qa_verifier`, or `worker_executor` by default.
- Files access is rooted; parent path components are opened with directory file descriptors and `O_NOFOLLOW`, and writes use a temporary file plus atomic rename.
- Connector task permissions are checked at call time. Task input cannot grant itself roles, scopes, or connector permissions.
- Durable audit persistence is fail-closed. If a mutating action may have occurred but its receipt cannot be persisted, result is UNKNOWN and replay is blocked.
- Never place tokens, private memory, or transcripts in repository files or GitHub issues.

## 3. CI evidence — exact heads, not production claims

| Work item | Exact head / merged commit | Evidence | What it proves |
|---|---|---|---|
| PR #91 intake persistence | reviewed head `813a3e1183ec968dd8f4536e68129212672774f1`; merge `92f411c56a21f0b3eb2b7c8373aed9900b463e96` | Runtime Registry: 478 tests, 1 skipped; OS compliance PASS | Offline persistence/fault-injection behavior only |
| PR #93 connector contract | merged as `57e09ba54f6ddb862cb810b38d0ab088681e3c7a` | Exact merge-ref CI after hardening: 501 tests, 1 skipped; OS compliance PASS | Unit/fixture behavior; no live authenticated connector |
| PR #103 native connectors | merged as `8026a3a47cf688684e3cfd662ee37c14ce279ce9` | Exact-head CI: 514 tests, 1 skipped; OS compliance PASS | Local process/filesystem fixture behavior; E2E simulation reports `actual_agent_spawned=false`, `external_network_calls=0` |
| PR #104 repository hygiene | merged as `16920b5f21173b2fe8e90dfac0003ddbd8410304` | Exact-head OS compliance PASS | Policy/configuration syntax only; not proof Dependabot has run |

## 4. Open connector work and disposition

- #92 old stage-0 inventory document is superseded by this current-baseline report.
- #94 old stacked branch is superseded by #103; #103 is the merged mainline implementation.
- #95 old security-hygiene branch is superseded by #104; #104 is merged.
- #96 public GitHub reader remains unmerged and must be rebased onto current main before acceptance. It must remain explicitly public/read-only; no private-repository or write capability may be inferred.
- #97 self-check remains unmerged and stale. Rebase onto current main; update expected counts/permissions after #103; keep authenticated integration as UNVERIFIED until a real credential-backed test exists.
- No connector PR may be called operational solely because unit tests or synthetic E2E simulations pass.

## 5. ChatGPT ↔ Codex host access

- [B] Issue #100 is not connected. The signed-in ChatGPT UI showed a Tunnel option, but save and tool invocation on this account were not verified. Platform inspection showed no tunnel, no API keys, and no billing method; cost/free eligibility remains unknown.
- [V] Issue #98 host inspection found Codex CLI 0.172.0 on the existing Cloud Shell host, outside default PATH. Cloud Shell is session-limited, not 24/7.
- [V] The revised #98 design was accepted as a separate experimental host-executor, not a model-provider backend. It must preserve the native HTTP default, use read-only first, per-task worktrees, process-group cleanup, bounded/redacted JSONL, and UNKNOWN/no-auto-replay after an incomplete intent.
- [B] Cloud Shell has no GitHub CLI authentication, so it cannot currently push branches or publish PRs itself. No host-side publication or live runner has been proven.

## 6. Remaining acceptance sequence

1. Rebase and independently review #96 on current main; keep it public/read-only and prove redirect, response-size, timeout, rate-limit, and no-auth-header behavior.
2. Rebase #97 on current main and update it to the merged connector implementation. A self-check must report skipped/blocked/unverified distinctly; never turn missing auth into PASS.
3. Complete #98's read-only CLI JSONL contract capture and isolated host-executor implementation. Preserve the no-GitHub-auth publication blocker; do not call local-only proof end-to-end.
4. Resolve #100 only if a supported, zero-cost ChatGPT-callable bridge can be proven. Do not create a tunnel, key, payment method, or paid resource without verified eligibility.
5. Demonstrate one real, explicitly opted-in task with correlated task/run/branch/receipt IDs, cancellation, restart recovery, and private persistence before claiming durable autonomy.
6. Add independent model-agent invocations only after distinct run IDs, fresh contexts, separate permissions, and correlated receipts are proven.

## 7. Preserved constraints

- Native-first; no Forge, OpenHands, or TinyFish runtime dependency.
- GitHub remains the source of truth.
- Free-first; no new paid host, service, or subscription assumed.
- No auto-merge. Merge only after exact-head code review and verification.
- Phone-first owner workflow; no laptop/IDE requirement for the owner.
