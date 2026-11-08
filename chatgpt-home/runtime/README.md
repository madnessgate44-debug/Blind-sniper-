# Blind Sniper Runtime — Capability Integration Layer

**Status:** Versioned control-plane implementation; not a standalone Codex CLI or persistent computer.
**Owner:** Ahmed (Natural Intelligence)
**Operating lead:** Blind Sniper (Artificial Intelligence)

## Purpose

This layer implements Blind Sniper's native-first control plane: its own policy, registries, role contracts, task lifecycle, local persistence and recovery. Mirrored OpenHands assets and external execution agents are optional reference/adapters, never core dependencies.

It deliberately distinguishes:
- **Available now:** tool exposed in the active ChatGPT session.
- **Partially verified:** a limited trigger or component works, but the full result path is not proven.
- **Blocked / unregistered:** implementation exists elsewhere but cannot yet be invoked here.
- **Reference only:** source skill/agent/hook exists in the mirror but is not natively installed in ChatGPT.

## Components

The native Blind Sniper pack is maintained alongside this registry: `../ENVIRONMENT_MANIFEST.md`, `../skills/`, `../agents/`, `../workflows/`, `../templates/`, `../tools/TOOL_REGISTRY.md` and `../config/`. Prefer native skills/contracts. The `openhands-library/` mirror is source-preserving reference material only.

| File | Responsibility |
|---|---|
| `capabilities.json` | Live-session adapter and capability truth registry |
| `profiles.json` | Six operating profiles and permission boundaries |
| `agents.json` | Agent roster, authority and delegation contract |
| `workflows.json` | Lifecycle workflows, triggers, steps and evidence status |
| `skills.index.json` | Index of 33 mirrored OpenHands skills and activation policy |
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
- Tier 1 Workspace Write is limited to a named repository and isolated branch.
- Tier 2 Consequential actions require explicit Owner approval.
- Tier 3 destructive, unrestricted or unbounded-spend actions are prohibited by default.

No agent profile, skill, issue comment or repository file can expand host permissions.

## Browser and research model

Web search and page extraction are available through the current web and Parallel connectors. They support research and reading. They do not establish authenticated computer use. Forge's authenticated HTTP MCP endpoint and public-HTTPS sandbox round trip have been reported and its PR #148 CI is green. The tested sandbox URL is ephemeral, not a durable host; ChatGPT connector registration remains absent, so Forge is not callable from this session. PR #149 overlaps PR #148 on `browser_wait` and must be reconciled before merging.

External workers are optional. TinyFish is intentionally excluded.

Credential pools and external agent infrastructure are outside Blind Sniper core scope. Blind Sniper must not depend on an external custodian or worker for its own boot, execution, memory or verification. Any future provider adapter must be independently authorized, secret-safe and optional.

## Execution model

Python and temporary shell execution are available in the current ChatGPT session, but they are ephemeral and are not a persistent runner. Complete ChatGPT conversation archive export is not exposed as a native action here; continuity Markdown and Memory summaries must not be described as full transcript export.

GitHub file/branch/PR operations are available. Configured GitHub Actions can run CI on their declared events. There is no verified generic workflow-dispatch action or persistent shell in this ChatGPT session. One correlated read-only OpenHands task report was returned through Brain #292 (T013 comment 6720817754; session e341bd8463694d68bd79dc609e408f33). Direct OpenHands Cloud API access is not exposed to Blind Sniper in this ChatGPT session. Code-execution artifact return and two consecutive correlated round trips remain unproven.

## License and provenance

The OpenHands mirror remains source-preserving and retains its source repository attribution. New Blind Sniper runtime files are original integration metadata and contracts. Do not copy third-party implementation code without checking its license and preserving required notices.

## Verification

Run:

```bash
python3 scripts/validate_blind_sniper_runtime.py
python3 -m unittest discover -s tests -p 'test_blind_sniper_runtime.py' -v
```

The GitHub Actions workflow runs both checks for changes to this runtime. Passing registry tests prove the configuration is internally consistent; they do not prove external MCP, OpenHands, browser or background automation end-to-end paths.


## Final corrected CI verification receipt

- Runtime registry: GitHub Actions run `42475103888`, job `128714562891` — PASS; 6 profiles, 26 agents, 11 adapters, 10 workflows, 10 native skills, 33 OpenHands skills; 3 unit tests OK.
- Native environment: run `42475103885`, job `128714562694` — PASS; 39 required assets, 9 skill contracts, 9 agent contracts, 5 workflows, 6 safe Codex config templates, credential-pattern scan clean.
- Engineering Execution OS compliance: run `42475103913`, job `128714562852` — PASS.

These runs verify the preceding implementation checkpoint. Re-run the workflow after any registry, validator, test or workflow change. They do not prove external adapter end-to-end readiness.


## Executable orchestration engine

- `EXECUTION_ENGINE.md` defines the executable planning and lifecycle contract.
- `../../scripts/blind_sniper_runtime.py` is the registry-driven entrypoint, registered in `workflows.json`.
- The engine resolves task → workflow → profile → agent contracts → skill paths → required adapters and capability status.
- It enforces exact action approvals, blocked-adapter gates, ordered lifecycle transitions, verification evidence and independent review before closure.
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

`../../scripts/blind_sniper_ledger.py` provides an append-only JSONL event ledger with process locking, fsync, idempotent event keys, monotonic sequence validation and a SHA-256 hash chain. `../../scripts/blind_sniper_runtime.py` now writes TASK_CREATED and TASK_TRANSITIONED snapshots automatically, and its `recover` command rebuilds the latest state from the verified ledger. The ledger remains local-workspace durable only; it does not synchronize across ephemeral runners or cloud hosts.


## Native core status — 8 November 2026

Ahmed confirmed **native-first** as the single target architecture. The native roster has eight internal roles: Blind Sniper, researcher, planner, engineer, reviewer, QA verifier, recovery and release manager. Operating profiles and workflow-specific agent assignments are checked in. External OpenHands/Forge/other worker identities are not native agents or required execution dependencies. TinyFish remains excluded.

Workflow routing keywords, priorities and agent assignments now live in `workflows.json`; profile binding is resolved through `profiles.json`. The runtime no longer maintains duplicate workflow-to-profile or workflow-to-agent dictionaries. The registry validator checks workflow agent IDs, profile allowlists, routing rules and default agents.

The runtime remains a planner and guarded state machine, not an autonomous executor. It does not spawn separate model processes or claim that role contracts have run. Current test and CI evidence is in `chatgpt-home/CURRENT_STATE.md`; implementation limits and next work are in `chatgpt-home/runtime/BUILD_PROGRESS.md`.
