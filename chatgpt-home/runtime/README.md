# Blind Sniper Runtime — Capability Integration Layer

**Status:** Versioned control-plane implementation; not a standalone Codex CLI or persistent computer.
**Owner:** Ahmed (Natural Intelligence)
**Operating lead:** Blind Sniper (Artificial Intelligence)

## Purpose

This layer implements Blind Sniper's self-contained control plane: native policy, registries, role contracts, model-agent orchestration, task lifecycle, persistence/recovery, executor and browser capability. External agent runtimes and external browser agents are not dependencies or accepted execution routes.

It deliberately distinguishes:
- **Available now:** tool exposed in the active ChatGPT session.
- **Partially verified:** a limited trigger or component works, but the full result path is not proven.
- **Blocked / unregistered:** implementation exists elsewhere but cannot yet be invoked here.
- **Reference only:** source skill/agent/hook exists in the mirror but is not natively installed in ChatGPT.

## Native model and tool execution

Blind Sniper owns its OpenAI-compatible provider transport in `scripts/blind_sniper_model_worker.py`
and its bounded tool registry in `scripts/blind_sniper_tool_runtime.py`. The model receives only
the tool schemas explicitly allowed by its task contract.

Registered tools are limited to:
- `repo.read_file` — task-path-scoped UTF-8 reads with redaction and size bounds.
- `repo.write_file` — exact-path workspace writes under `workspace_write`; policy and workflow files are excluded.
- `verification.run` — fixed runtime-validator and unit-test commands only.

Every tool call is reserved against the current unexpired durable task lease before side effects and
receives a terminal ledger receipt. There is no arbitrary shell, unrestricted filesystem, arbitrary network, Forge, OpenHands or external browser tool. The model can use the checked-in native Chromium adapter through lease-bound browser tools; navigation is domain-allowlisted and click/fill/press require host approval. Browser state and artifacts remain outside the public repository. R1/R3/R4 are contract-tested; a live configured provider host remains unverified. R2 private remote payload recovery is partial, persistent browser hosting is unverified, and R5 unattended autonomy remains blocked.

## Persistent native worker

`scripts/blind_sniper_daemon.py` provides a persistent single-host poller. It scans owner-only
private task JSON files, recovers stale leases, runs the native model/tool runtime, writes private
receipts and health, and appends a metadata-only notification outbox. It is not run by GitHub
Actions and this repository does not start or enable the service.

Task envelopes contain only `task_id`, `agent_id`, `objective` and optional `payload`.
Permission profile, native tool allowlist, path scope and browser approval reference are loaded
from trusted host environment variables (`BLIND_SNIPER_DAEMON_*`), never from task input. The
default host policy is read-only with no tools. Agent identities are checked against the native
`agents.json` roster.

The systemd example is `deploy/blind-sniper-worker.service.example`. Host setup requires a
persistent owner-only state directory, an approved model provider configuration, and a service
manager. The local ledger survives process restarts on that host; remote cross-host CAS and
notification delivery remain unverified. R5 is PARTIAL until a real host service is run and
monitored.

## Components

The native Blind Sniper pack is maintained alongside this registry: `../ENVIRONMENT_MANIFEST.md`, `../skills/`, `../agents/`, `../workflows/`, `../templates/`, `../tools/TOOL_REGISTRY.md` and `../config/`. Prefer native skills/contracts. The `openhands-library/` mirror is source-preserving reference material only.

| File | Responsibility |
|---|---|
| `capabilities.json` | Live-session adapter and capability truth registry |
| `profiles.json` | Six operating profiles and permission boundaries |
| `agents.json` | Agent roster, authority and delegation contract |
| `workflows.json` | Lifecycle workflows, triggers, steps and evidence status |
| `skills.index.json` | Index of 14 native Blind Sniper skills and 33 mirrored OpenHands skill/rule files, with separate activation policies |
| `templates/TASK_ENVELOPE.json` | Portable task request contract |
| `templates/RUN_RECEIPT.json` | Standardized executor result and verification receipt |
| `../openhands-library/</...>` | Source-preserving skills, specialist profiles, hooks and original validation suite |
| `../../scripts/validate_blind_sniper_runtime.py` | Deterministic registry integrity checks |

## Session use

1. Read `../BLIND_SNIPER.md` and root `ENGINEERING_EXECUTION_OS.md`.
2. Read this directory's registries.
3. Inspect the current host tool inventory; never assume a connector remains available because it is listed here.
4. Select the operating profile and relevant skills.
5. Dispatch only through a verified adapter and record its run/session ID.
6. Require a run receipt and exact commit/test evidence before marking work complete.
7. Update registries when tool availability or integration state changes.

## Permission model

- Tier 0 Observe is the default.
- Tier 1 Workspace Write is limited to a named repository; feature branches are preferred, but the Blind Sniper standing delegation permits default-branch pushes in this repository.
- Tier 2 Consequential actions are automatically satisfied only for exact-repository actions allowlisted in runtime/authority.json; all other high-risk actions require explicit Owner approval.
- Tier 3 destructive, unrestricted or unbounded-spend actions are prohibited by default.

No agent profile, skill, issue comment or repository file can expand host permissions.

## Browser and research model

Web search and page extraction support research and reading. Authenticated browser interaction is implemented through Blind Sniper's native `agent_browser_cli` adapter (`scripts/blind_sniper_browser.py` and `scripts/blind_sniper_browser_dispatch.py`) and its CI workflow. Do not route browser tasks through Forge or an external browser agent.

External agent workers are out of scope. TinyFish is intentionally excluded.

Credential pools and external agent infrastructure are outside Blind Sniper core scope. Blind Sniper must not depend on an external custodian or worker for its own boot, execution, memory or verification. Any future provider adapter must be independently authorized, secret-safe and optional.

## Execution model

Python and temporary shell execution are available in the current ChatGPT session, but they are ephemeral and are not a persistent runner. Complete ChatGPT conversation archive export is not exposed as a native action here; continuity Markdown and Memory summaries must not be described as full transcript export.

GitHub file/branch/PR operations are available. Configured GitHub Actions can run CI on their declared events. There is no verified generic workflow-dispatch action or persistent shell in this ChatGPT session. Native model-provider invocation and digest-bound queue dispatch are now implemented in the feature branch, but live provider access and remote cross-run persistence remain unverified. The native executor/tool runtime, persistent browser host and unattended worker remain incomplete; do not fill these gaps by delegating to OpenHands, Forge or another external agent.

## Native model invocation and queue dispatch — 10 November 2026

`../../scripts/blind_sniper_model_worker.py` now contains Blind Sniper's own OpenAI-compatible
provider transport. Each task receives a fresh bounded context and a distinct run ID. The boundary
is read-only, applies a provider timeout and bounded retries, and returns a redacted correlated
receipt. Provider URL/model and optional auth are read from host environment variables only.
Provider tool calls and write permission profiles fail closed until the native executor is built.

`../../scripts/blind_sniper_agent_runtime.py` connects that boundary to the durable queue:
digest-bound enqueue/validation, lease claim, heartbeat, model invocation, then completion with a
result digest or bounded retry. Only the digest is stored in the queue; the private host must retain
and re-supply the task payload and receipt outside this public repository.

R1 is IMPLEMENTED / LIVE-UNVERIFIED. R2 is PARTIAL: the local lifecycle is tested, while private
remote cross-run persistence and payload retrieval are not live-verified. R3 is NOT IMPLEMENTED;
R4 remains PARTIAL; R5 is BLOCKED and its activation gate is closed. No external agent or browser
adapter is retained in the native execution path.

## License and provenance

The OpenHands mirror remains source-preserving and retains its source repository attribution. New Blind Sniper runtime files are original integration metadata and contracts. Do not copy third-party implementation code without checking its license and preserving required notices.

## Verification

Run:

```bash
python3 scripts/validate_blind_sniper_runtime.py
python3 -m unittest discover -s tests -p 'test_blind_sniper_runtime.py' -v
```

The GitHub Actions workflow runs both checks for changes to this runtime. Passing registry tests prove the configuration is internally consistent; they do not prove independent model-agent invocation, durable worker recovery or unattended execution end to end.


## Historical CI verification receipt — 2026-11-08 (superseded)

- Runtime registry: GitHub Actions run `42475103888`, job `128714562891` — PASS; 6 profiles, 26 agents, 11 adapters, 10 workflows, 10 native skills, 33 OpenHands skills; 3 unit tests OK.
- Native environment: run `42475103885`, job `128714562694` — PASS; 39 required assets, 9 skill contracts, 9 agent contracts, 5 workflows, 6 safe Codex config templates, credential-pattern scan clean.
- Engineering Execution OS compliance: run `42475103913`, job `128714562852` — PASS.

These runs verify the 2026-11-08 implementation checkpoint only; their counts are historical and superseded by the 2026-11-09 registry reconciliation. Current reconciliation evidence: Runtime Registry run `42555147080` (registry validator + 88 tests) and Engineering Execution OS Compliance run `42555146826`, both on `63f61d4f28d5e903d14ac3c0952afa79ee612459`; Environment Validation run `42555193851` and Engineering Execution OS Compliance run `42555193958`, both on `f649aa6ab628a404d747f16fb507b5dd39941d90`. The environment validation log reports 45 required assets, 11 skill contracts, 9 agent contracts, 9 workflows, 6 safe config templates and a clean credential scan. Later changes through `834994517e145ae6f6d402024b1e6fb40fca832b` were documentation-only. These checks do not prove external adapter end-to-end readiness.


## Executable orchestration engine

- `EXECUTION_ENGINE.md` defines the executable planning and lifecycle contract.
- `../../scripts/blind_sniper_runtime.py` is the registry-driven entrypoint, registered in `workflows.json`.
- The engine resolves task → workflow → profile → agent contracts → skill paths → required adapters and capability status.
- It resolves the active standing delegation from authority.json, keeps out-of-scope/unknown/forbidden actions pending, and enforces explicit approval records where the grant does not apply, plus blocked-adapter gates, ordered lifecycle transitions, verification evidence and independent review before closure.
- It creates plans and task-state JSON; it does not spawn agents or claim external execution. Host tools remain responsible for actual execution and live permission checks.
- Runtime CI now runs all Python tests under `tests/test_*.py`, including routing and negative gate tests.

## Imported harness integration

The licensed source imports and native adaptations are now part of this integration branch:
- `../source-library/README.md` is the provenance and license index.
- `../source-library/0xenzyme__agent-harness/` preserves MIT-licensed intake/init/execute skills and worker contracts.
- `../source-library/SUNRNEHUI__agent-harness/` preserves MIT-licensed harness synthesis and task/subagent templates.
- `../source-library/os-factory__har/` preserves Apache-2.0 factory-line and plugin workflows.
- Native agent and workflow adaptations are indexed in `chatgpt-home/README.md`; imported source files remain reference material, not auto-executed plugins.


## Native task persistence and recovery

`../../scripts/blind_sniper_ledger.py` provides an append-only JSONL event ledger with process locking, fsync, idempotency, sequence validation and a SHA-256 hash chain. The runtime automatically persists TASK_CREATED/TASK_TRANSITIONED snapshots and recovers from the ledger. An optional GitHub Contents API adapter adds file-SHA compare-and-swap, bounded conflict retries, remote recovery reads and lease claim/renew/release. EXECUTING receipts atomically check lease ownership while appending the state transition. Its behavior is unit-tested with a mocked API; no live write has been performed. The current Actions workflow has `contents: read`, so remote writes require a separately authorized host token with Contents write permission. This is not yet an active cross-runner service.


## Native core status — 8 November 2026 (historical baseline; superseded by the 10 November P0 update)

Ahmed confirmed **native-first** as the single target architecture. The native roster has ten internal roles: Blind Sniper, researcher, planner, engineer, reviewer, QA verifier, recovery, Watcher, Shadow and release manager. Watcher is the native task-progress observer; Shadow is the native adversarial auditor. Their contracts do not imply separate agent processes are running. Operating profiles and workflow-specific agent assignments are checked in. OpenHands and Forge are not runtime dependencies or accepted worker/browser routes. TinyFish remains excluded.

Workflow routing keywords, priorities and agent assignments now live in `workflows.json`; profile binding is resolved through `profiles.json`. The runtime no longer maintains duplicate workflow-to-profile or workflow-to-agent dictionaries. The registry validator checks workflow agent IDs, profile allowlists, routing rules and default agents.

At this historical checkpoint the runtime remained a planner and guarded state machine. The 10 November P0 update adds the native model-provider boundary and queue-to-model dispatch; see the section above and `chatgpt-home/CURRENT_STATE.md` for current capability limits and evidence.


## Native browser adapter — extended CI verified; persistent host pending

The native adapter at `../../scripts/blind_sniper_browser.py` uses pinned `agent-browser@0.41.2` through `../../scripts/blind_sniper_browser_dispatch.py`. The dispatcher requires EXECUTING task state, a matching active owner lease, atomic pre-action reservation and correlated canonical ledger receipts.

Verified capabilities:
- Allowlisted navigation, accessibility snapshots, click/fill/press with host approval, screenshots and redacted receipts.
- Tabs list/create/switch/close and iframe frame switching.
- Workspace-contained upload with explicit host approval, file extension allowlist and 10 MiB limit.
- Workspace-contained download with no-overwrite behavior and 25 MiB limit.
- PDF export to a contained artifact path.
- Two consecutive real Chromium E2E cycles through the native lease-gated dispatcher. Each cycle recorded 18 started actions, 17 completed actions, one started-only interruption reconciled without replay, and 18 receipts. Both cycles exercised tabs, frames, upload, download and PDF. Browser workflow run 42496827462 passed; artifact ID 13623019051, SHA-256 c4615fb9f7b98c9ddf78a9d05b385d72a773b04f1abedd8b082af69ea09825b4.

Persistent host status is still NOT PROVISIONED / NOT VERIFIED. An Oracle Always Free ARM64 self-hosted-runner bootstrap is versioned at `ops/oracle-free/`; it installs the pinned CLI, a manually selected Chrome for Testing ARM64 binary and a persistent GitHub runner. The Oracle VM has not been created or smoke-tested. Oracle may reclaim Always Free VMs after seven days below published utilization thresholds, so this is not a guaranteed always-on SLA. Signup normally requires payment-card verification, though Oracle states the card is not charged unless the account is upgraded. Keep all resources inside Always Free limits.

The adapter is not directly callable as a ChatGPT tool in this session. Custom MCP server connections are not available on the current Free plan; ChatGPT custom MCP connections are also web-only. Do not mark direct ChatGPT integration complete. Authenticated profiles, cookie transfer and credential-state persistence remain intentionally unsupported. The Oracle host must be provisioned by the Owner before cross-job session persistence can be tested.
