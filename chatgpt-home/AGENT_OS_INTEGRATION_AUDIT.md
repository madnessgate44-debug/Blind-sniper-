# BS-OS-001 — GitHub Agent OS Integration Audit

**Status:** COMPLETED — static repository/reference audit; runtime activation is not certified  
**Audit date:** 2026-11-09  
**Repository:** `madnessgate44-debug/Blind-sniper-`  
**Baseline:** `main` at `ac8a5eb5f7b3eaf02be73733c7f49e53106da69e`  
**Audit branch:** `audit/bs-os-integration-2026-11-09`  
**Scope:** Blind Sniper operating-system assets, imported libraries, four selected upstream references, registry consistency, runtime activation boundaries and provenance. No other product repository was modified.

## 1. Executive result

Blind Sniper already contains a substantial native operating layer. It is not a blank repository and does not need a wholesale replacement with a third-party Claude Code framework.

The current architecture is **native-first**: canonical policy, native role contracts, skill and workflow registries, a guarded task-state runtime, a local append-only ledger, and optional external adapters. OpenHands is preserved as a source mirror; three additional licensed harness sources are selectively imported. The native runtime documentation explicitly states that the engine plans and gates work but does not spawn separate model processes.

The integration is therefore **substantially assembled as a control-plane specification, but only partially operational as an agent OS**. The remaining work is not “copy all four repositories.” It is to reconcile the native catalogs, adapt the useful upstream patterns that are genuinely missing, and verify real execution adapters separately.

### Main findings

1. The OpenHands import is integrity-consistent with its recorded source snapshot: 68 source files match their original Git blob SHAs. The import is a reference mirror, not an OpenHands runtime installation.
2. The selected Showcase and Mendelevium repositories resolve to the same Git tree SHA and the same README blob SHA. They are duplicate content, not two independent frameworks.
3. The selected `mattzcarey/claude-code-agent-framework` path returns GitHub 404. A separate repository, `mattzcarey/shippie`, exists but is a code-review/QA agent project; it is not silently substituted.
4. Ralph is not imported. Its PRD decomposition and iteration-memory ideas are useful, but its shell runner invokes Amp/Claude with dangerous permission-bypass flags and must not be copied into Blind Sniper unchanged.
5. Native catalogs have drift: four agent files are unregistered, one native skill file is unindexed, four workflow documents are not referenced by the workflow registry, and six registry workflows have no contract path.
6. Current-state documentation is stale relative to the merged PR #17 and the current main commit.
7. Public continuity files remain in this public repository even though the canonical Blind Sniper instructions prohibit reading or copying them and state that private memory storage has not been created. Their contents were not read during this audit.

## 2. Baseline and governing authority

| Evidence | Result |
|---|---|
| Root `AGENTS.md` | Retrieved; requires reading the root Engineering Execution OS and the full execution lifecycle |
| `ENGINEERING_EXECUTION_OS.md` | Retrieved; v2.2 governs execution, evidence, read-only defaults and approval gates |
| `chatgpt-home/BLIND_SNIPER.md` | Retrieved; v3.0 declares native-first architecture and ten canonical roles |
| Repository default branch | `main` |
| Main HEAD | `ac8a5eb5f7b3eaf02be73733c7f49e53106da69e` |
| Main tree SHA | `e16483e744b4dc079a8e41d12833b41ab7f1c54c` |
| Tracked tree entries | 314 (214 blobs) |

The current `main` commit is the merge commit for PR #17. GitHub confirms PR #17 merged at 2026-11-09 02:40:51 UTC, with merge commit `ac8a5eb5f7b3eaf02be73733c7f49e53106da69e`. The integration branch head is `802e01bd636c9610cadd76a80eb8423b256866f4`; comparing it with main shows main is one commit ahead and the file trees are identical.

**Stale-state defect:** `chatgpt-home/CURRENT_STATE.md` records a 02:31 UTC snapshot, says PR #17 is open/not merged, and says main does not yet contain the consolidated runtime. Those statements became stale after the 02:40:51 UTC merge. Use current GitHub state, not that stale prose, as the source of truth until the state file is reconciled.

Root `README.md` currently describes the Miss Noor static preview. The operating system is intentionally housed under `chatgpt-home/`; preserve the root product and do not repurpose it during this OS work.

## 3. Inventory of the native Blind Sniper OS

### 3.1 Canonical control plane

Present on main:

- Identity and authority: `chatgpt-home/BLIND_SNIPER.md`, `BLIND_SNIPER_OS.md`, root `AGENTS.md`, root `ENGINEERING_EXECUTION_OS.md`.
- Profiles and registries: `runtime/profiles.json`, `agents.json`, `skills.index.json`, `workflows.json`, `capabilities.json`.
- Native role contracts: `chatgpt-home/agents/`.
- Native skills: `chatgpt-home/skills/`.
- Workflow contracts: `chatgpt-home/workflows/`.
- Hooks/guards and MCP/browser contracts: `hooks/HOOKS_AND_GUARDS.md`, `mcp/MCP_AND_BROWSER_INTEGRATIONS.md`.
- Runtime implementation: `scripts/blind_sniper_runtime.py`, `scripts/blind_sniper_ledger.py`, and browser adapter scripts.
- Validation and tests: `scripts/validate_blind_sniper_runtime.py`, environment and OS compliance checks, and `tests/`.

### 3.2 Registry and file-count reconciliation

| Area | Files on main | Registry/catalog declaration | Audit result |
|---|---:|---:|---|
| Profiles | 6 | 6 | Aligned |
| Runtime agent IDs | 10 | 10 | Canonical roster is defined |
| Agent markdown profiles | 13 (excluding README) | 10 registered | 4 unregistered files |
| Native skill files | 11 | 10 indexed | `github-research` is unindexed |
| Native workflow documents | 9 (excluding README) | 13 workflow entries | 4 docs unreferenced; 6 workflow entries have no contract path |
| Capability adapters | — | 13 | Registry exists; entries still require live verification |

**Unregistered agent files:**

- `chatgpt-home/agents/factory-orchestrator.md`
- `chatgpt-home/agents/harness-controller.md`
- `chatgpt-home/agents/independent-reviewer.md`
- `chatgpt-home/agents/worker-executor.md`

These have meaningful source origins, but they are not part of the ten-role canonical runtime roster. Some overlap with registered roles: harness-controller with Blind Sniper, independent-reviewer with reviewer/Shadow, and worker-executor with engineer. Keep them as reference/adaptation material until an explicit decision either registers them with distinct responsibilities or marks them non-runtime templates. Do not silently add duplicate agents.

**Unindexed native skill:**

- `chatgpt-home/skills/github-research/SKILL.md` exists but is absent from `runtime/skills.index.json` and the native skill list in the index.

The skills README lists nine skills and omits the continuity skill; the runtime index lists ten and omits github-research. `SKILLS_CATALOG.md` also describes an earlier nine-skill pack. These indexes need one canonical reconciliation.

**Workflow drift:**

- Four workflow documents are not referenced by any `native_contract_path`: `idea-to-contract.md`, `isolated-execution-line.md`, `plugin-and-tool-onboarding.md`, and `verification-and-handoff.md`.
- Six of the thirteen runtime workflow entries have no `native_contract_path`: research-and-synthesis, forge-browser-roundtrip, persistent-browser-host-acceptance, continuous-autonomy, conversation-archive-export, and native-browser-acceptance.
- The workflow README lists only five workflows.

Some registry-only workflows may intentionally be executable contracts assembled from other files, but that ownership is not explicit. Add a clear contract/reference for each or mark it intentionally registry-only.

**Agent metadata defect:** the `release-manager` registry entry identifies its source as `openhands-library` and status as `reference_profile_present`, while also pointing to a native `chatgpt-home/agents/release-manager.md` contract. Clarify whether it is a native adaptation, a source mirror role, or both.

**Stale environment counts:** `ENVIRONMENT_MANIFEST.md` and `SKILLS_CATALOG.md` retain earlier nine-skill/nine-agent/five-workflow counts. They should be treated as historical snapshots, not the current catalog.

## 4. OpenHands import audit

**Manifest:** `chatgpt-home/openhands-library/IMPORT_MANIFEST.md`  
**Recorded source:** `madnessgate44-debug/Openhands`, main tree `ea9f6151e2d1524d8413b1b7994556a7f5495929`  
**Destination:** `chatgpt-home/openhands-library/`

The recorded source tree contains 70 blobs. The mirror contains 69 blobs: 68 intended source files plus the Blind Sniper import manifest. Comparing the 68 intended files against the recorded source tree produced:

- 68 exact blob-SHA matches;
- 0 content mismatches;
- 2 source files intentionally not mirrored: `.gitignore` and `docs/AUDIT_REPORT_2026-10-26.md`;
- 1 destination-only file: `IMPORT_MANIFEST.md`.

The imported library includes 33 skill/rule files, 19 specialist agent profiles, hook definitions and scripts, manifests, documentation, validation scripts, tests and a workflow. The three lifecycle hook behaviors are represented by five hook-related files (configuration plus scripts).

**Important runtime boundary:** the mirror is not an installation of OpenHands. Its manifests, SDK loader, hooks, sub-agents and workflow do not execute inside ChatGPT. Blind Sniper's native OS correctly describes the mirror as reference material and says selected skills must be retrieved explicitly.

The live OpenHands main tree now has SHA `bd4011cc1a36a8e0169ec82dbb43ce50d05ae18b`, different from the imported snapshot. No automatic upstream synchronization is present or claimed. Preserve the import as a pinned snapshot and use an explicit update review if refreshing it.

## 5. Audit of the four selected upstream references

| Selected source | Repository evidence | Present in Blind Sniper? | Decision |
|---|---|---|---|
| `ChrisWiles/claude-code-showcase` | Public main tree SHA `a95518f0cb67e86230119da40429169bc4c35a6f`; README SHA `43a3fad0ec37545d1039dec81561e9515323de1e`; README describes MIT template use | No verbatim `.claude/` import found | ADAPT host-neutral patterns; do not copy Claude-only hooks/config as if ChatGPT can run them |
| `mattzcarey/claude-code-agent-framework` | Exact repository/tree request returned GitHub 404; exact-name repository search returned no result | No | BLOCKED: source identity must be confirmed; do not substitute another repository |
| `snarktank/ralph` | Public main tree SHA `6c53cb0b831ebe8739c6a003e22af14902d8b0b5`; MIT license | No Ralph runner/files found | ADAPT PRD/story and iteration-memory concepts; reject unsafe runner defaults |
| `mendelevium/claude-code-config` | Public main tree SHA is exactly the same as the Showcase tree; README blob SHA is also identical | No verbatim import found | DUPLICATE of Showcase content, not an independent framework. Reconcile the source-library license note before relying on it |

### 5.1 Showcase / Mendelevium — useful patterns and gaps

The Showcase supplies a reusable skill-matching engine, skill rules, agent contracts, slash-command workflows, hook configuration, a code-review agent, and PR/scheduled maintenance workflows.

Blind Sniper already has native agents, skills, workflow routing, permission profiles and GitHub Actions validation. The useful remaining gap is **skill selection assistance**: the current native index says Blind Sniper retrieves selected skills explicitly; there is no imported Showcase skill-evaluation engine or equivalent automatic selector in the native skill directory.

The Showcase also demonstrates:
- PR-triggered AI review;
- scheduled documentation alignment;
- scheduled code-quality review;
- scheduled dependency audits.

Blind Sniper currently has four root GitHub workflows for browser acceptance, environment validation, runtime validation and OS compliance. They are push/PR/manual validation workflows; there is no equivalent scheduled docs/quality/dependency workflow or Claude-style PR review action in the root workflow inventory.

**Adaptation warning:** the source's Claude Code hooks, `.claude/settings.json`, MCP settings and command files are host-specific. Blind Sniper must translate intent into its own registries and verified GitHub/ChatGPT tools. Do not import a hook script and label it active.

**License/provenance inconsistency:** the source-library README says Mendelevium has no declared license, but its README is byte-identical to Showcase's README and contains an MIT license statement. Neither repository tree contains a standalone `LICENSE` file, and GitHub's repository metadata did not expose a detected license. Record this as a license/provenance item requiring confirmation; do not represent Mendelevium as a separate source or copy its code on an unverified license assumption.

### 5.2 Ralph — useful patterns and unsafe implementation defaults

Ralph contributes:
- PRD → small, dependency-ordered user stories;
- explicit `passes` acceptance state per story;
- fresh model context per iteration;
- append-only progress learnings and Git history;
- bounded maximum iteration count and completion signal.

Blind Sniper has task envelopes, workflow plans, guarded lifecycle transitions, a local append-only JSONL ledger, task snapshots and recovery. Ralph's concepts can complement these structures; a parallel second task-state system should not be introduced.

**Do not copy `ralph.sh` unchanged.** It calls Amp with `--dangerously-allow-all` and Claude with `--dangerously-skip-permissions`. Those defaults conflict with Blind Sniper's least-privilege and explicit approval model. Reuse the PRD/story sizing and progress-memory concepts only behind the native task ledger, scoped execution adapter, verification and approval gates.

### 5.3 Mattzcarey source identity

The requested `mattzcarey/claude-code-agent-framework` could not be retrieved. `mattzcarey/shippie` is a separate public repository, but its description identifies it as an extendable code-review and QA agent, not the requested framework. It is not substituted in this audit. Confirm the intended repository before evaluating it.

## 6. Additional imported harness sources

Blind Sniper also selectively imports three sources beyond the four selected references:

| Source | Upstream tree SHA inspected | Imported files | License/provenance |
|---|---|---:|---|
| `0xenzyme/agent-harness` | `fc0e75e12a7332cfc660ee7b04592d1d6ed7f2f8` | 10 | MIT; imported file SHAs match upstream |
| `SUNRNEHUI/agent-harness` | `788f78a67a97d2197cb5a79c573c8b9b17897394` | 5 | MIT; imported file SHAs match upstream |
| `os-factory/har` | `aba54bf406ecba82d1ebf4f5e2c7c907665d788b` | 3 | Apache-2.0; LICENSE and both imported skills match upstream blob SHAs; upstream `.claude` paths are stored under destination `_claude` |

These are selective source imports, not full framework installations. Their assets include intake/init/execute skills, worker-runner and Codex execution references, task/sub-agent templates, and factory-line/plugin skills. Native adaptations exist for harness control, worker execution and factory orchestration. Keep the source copies separate from native contracts and retain license notices.

## 7. Runtime and integration truth

The runtime documentation and registries describe the following boundaries:

| Capability | Repository-declared state | Audit interpretation |
|---|---|---|
| Native planning and guarded task lifecycle | Implemented | Control-plane behavior exists; it is not a model-agent executor |
| Local append-only task ledger and recovery | Implemented/tested in repository history | Static audit did not rerun tests |
| GitHub-backed ledger | Mock-tested; live write not performed; public repository guard blocks writes | Not a live remote persistence service |
| OpenHands handoff | Partially verified | A limited mention/session route is documented; direct ChatGPT API dispatch/result retrieval is not a callable tool here |
| Forge browser MCP | Blocked/unregistered | No callable Forge browser tool in this session |
| Browser adapter | Native Chromium E2E evidence is recorded in repository state | CI browser acceptance is distinct from a persistent authenticated browser host |
| Persistent runner | Bootstrap documented, host not provisioned | Cross-job persistence is not verified |
| Continuous autonomy | Not verified | Do not claim unattended/background execution |
| ChatGPT history export | Blocked | No native export action is exposed |
| Independent Shadow execution | Contract exists | Distinct reviewer execution identity is not verified |

The four root workflows have read-only `contents: read` permissions. The browser workflow's self-hosted persistence jobs are owner-gated and require a configured self-hosted runner. No workflow permission expansion or external host provisioning is authorized by this audit.

## 8. Privacy and repository-boundary finding

The repository is public. The tree contains:

- `chatgpt-home/MEMORY.md`
- `chatgpt-home/PROJECTS.md`
- `chatgpt-home/CONVERSATION_CONTINUITY.md`

The canonical `BLIND_SNIPER.md` says not to read, quote, copy, index or migrate these public copies; it also says the proposed private-memory repository has not been created. Their contents were deliberately not fetched or inspected.

This is a **privacy/control-plane blocker** for any future memory integration. Do not use those public files as active private memory. Establish and verify private storage through an explicitly authorized path before resuming private continuity or transcript-archive work. Editing public files does not erase prior Git history.

## 9. Requirement-to-evidence mapping

| ID | Acceptance criterion | Result | Evidence / gap |
|---|---|---|---|
| R1 | Establish current governing OS and correct repository baseline | PASS | Root policy files fetched; main HEAD and PR #17 merge verified |
| R2 | Inventory native OS and its registries/assets | PASS | 314 tree entries; native registries, agents, skills, workflows and runtime inspected |
| R3 | Verify OpenHands mirror against its recorded source snapshot | PASS | 68/68 intended files exact blob-SHA matches; two exclusions documented |
| R4 | Evaluate all four selected references without substitution | PARTIAL | Showcase, Ralph and Mendelevium inspected; Mendelevium duplicates Showcase; Mattzcarey target 404 |
| R5 | Reconcile native registry-to-file integration | FAIL / GAP | 4 unregistered agent files, 1 unindexed skill, 4 unreferenced workflow docs, 6 workflows without contract paths |
| R6 | Establish real runtime activation boundaries | PARTIAL | Registry and documentation inspected; external adapter statuses remain partial/blocked/not verified |
| R7 | Confirm memory/privacy boundary | BLOCKED | Public continuity files exist; private storage not established; contents intentionally not read |
| R8 | Execute the repository's validation suite during this audit | NOT RUN | This was a static GitHub source audit; no shell/test runner was used |

## 10. Adoption decisions

| Component | Decision | Reason |
|---|---|---|
| Blind Sniper native policy/runtime/registries | KEEP as canonical | Already the controlling architecture; avoid a competing OS |
| OpenHands 68-file mirror | KEEP as pinned reference | Integrity verified; not executable inside ChatGPT |
| Showcase patterns | ADAPT selectively | Skill matching and scheduled quality/review patterns are useful; Claude hooks are not directly portable |
| Mendelevium config | DO NOT TREAT AS SEPARATE SOURCE | Same Git tree as Showcase; license metadata needs correction |
| Ralph PRD and progress concepts | ADAPT | Complements task decomposition and memory; avoid its dangerous permission-bypass runner |
| Mattzcarey framework | BLOCKED | Exact selected repository unavailable; do not silently substitute Shippie |
| 0xenzyme / SUNRNEHUI / os-factory imports | KEEP selectively | Imported files and license assets were checked against upstream blobs; native adaptations already exist |
| Four unregistered native agent profiles | RECONCILE | Keep files; explicitly register as distinct roles or label as non-runtime templates |
| github-research skill | RECONCILE | Register it or mark it as intentionally retired/reference-only |
| Workflow documents and registry | RECONCILE | Give each workflow an explicit contract/reference or an intentional registry-only status |

## 11. Recommended next work (not executed in this audit)

1. **BS-OS-001A — Registry reconciliation:** align agent, skill and workflow registries with actual files; resolve duplicates and stale counts; correct release-manager provenance/status.
2. **BS-OS-001B — Source identity/license reconciliation:** confirm the intended Mattzcarey repository; correct the Mendelevium/Showcase duplicate and license note.
3. **BS-OS-002 — Canonical architecture/adoption matrix:** keep native-first; map every adopted pattern to one owner, one path and one activation mechanism.
4. **BS-OS-003 — Selective adoption:** prioritize a host-neutral skill selector and PRD/story progress integration; do not import Claude-only hooks or Ralph's bypass runner.
5. **Separate privacy gate:** establish verified private storage before any memory/archive migration.
6. **Only after those gates:** return to generic execution engine work and external integration acceptance.

## 12. Verification ledger and limitations

| Check/action | Evidence | Result |
|---|---|---|
| Fetch root `AGENTS.md` and `ENGINEERING_EXECUTION_OS.md` from main | Blob SHAs `91d63a56818ebf5d757ac7cda0e0786fff88b058`, `7c339a090eaf23fc1e4f9112f72a4ba28f2bfe1c` | PASS — retrieval |
| Fetch recursive main tree | `ac8a5eb5f7b3eaf02be73733c7f49e53106da69e`; 314 entries | PASS — retrieval |
| Verify PR #17 and branch relationship | PR #17 merged; merge commit equals main HEAD; integration branch one commit behind with same tree | PASS — repository-state check |
| Compare OpenHands snapshot and mirror blob SHAs | 68 matches, 0 mismatches, 2 exclusions | PASS — source-integrity comparison |
| Compare selected reference repositories | Showcase/Mendelevium identical tree; Ralph distinct; Mattzcarey target 404 | PASS — retrieval; Mattzcarey remains blocked |
| Compare additional harness import blobs | 0xenzyme 10/10; SUNRNEHUI 5/5; os-factory 3/3 (path rename documented) | PASS — source-integrity comparison |
| Run Python/Node tests or GitHub Actions | Not run in this audit | NOT RUN |
| Inspect public continuity file contents | Intentionally not fetched under canonical privacy instruction | NOT RUN / prohibited |

This report is a static source and provenance audit. It does not certify runtime execution, external agent activation, private-memory availability, or production readiness.

## 13. Evidence references

- Main commit: https://github.com/madnessgate44-debug/Blind-sniper-/commit/ac8a5eb5f7b3eaf02be73733c7f49e53106da69e
- PR #17 merge: https://github.com/madnessgate44-debug/Blind-sniper-/pull/17
- OpenHands source: https://github.com/madnessgate44-debug/Openhands
- OpenHands mirror manifest: `chatgpt-home/openhands-library/IMPORT_MANIFEST.md`
- Showcase: https://github.com/ChrisWiles/claude-code-showcase
- Mendelevium: https://github.com/mendelevium/claude-code-config
- Ralph: https://github.com/snarktank/ralph
- Requested Mattzcarey path: https://github.com/mattzcarey/claude-code-agent-framework
- Separate Mattzcarey repository (not substituted): https://github.com/mattzcarey/shippie
- Additional sources: https://github.com/0xenzyme/agent-harness, https://github.com/SUNRNEHUI/agent-harness, https://github.com/os-factory/har
