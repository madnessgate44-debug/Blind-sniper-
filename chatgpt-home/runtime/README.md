# Blind Sniper Runtime — Capability Integration Layer

**Status:** Versioned control-plane implementation; not a standalone Codex CLI or persistent computer.
**Owner:** Ahmed (Natural Intelligence)
**Operating lead:** Blind Sniper (Artificial Intelligence)

## Purpose

This layer joins the existing OpenHands skill/agent library, Codex-inspired profiles, current ChatGPT connectors, GitHub workspaces, external execution agents and evidence workflows behind one capability registry.

It deliberately distinguishes:
- **Available now:** tool exposed in the active ChatGPT session.
- **Partially verified:** a limited trigger or component works, but the full result path is not proven.
- **Blocked / unregistered:** implementation exists elsewhere but cannot yet be invoked here.
- **Reference only:** source skill/agent/hook exists in the mirror but is not natively installed in ChatGPT.

## Components

The native Blind Sniper pack is maintained alongside this registry: `../ENVIRONMENT_MANIFEST.md`, `../skills/`, `../agents/`, `../workflows/`, `../templates/`, `../tools/TOOL_REGISTRY.md` and `../config/`. Prefer the native skills/contracts for this ChatGPT host. The `openhands-library/` mirror remains the broader source-preserving specialist library.

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

Web search and page extraction are available through the current web and Parallel connectors. They support research and reading. They do not establish authenticated computer use. Forge's HTTP MCP adapter remains blocked until a public HTTPS endpoint, authentication, tool allowlist, connector registration and live round trip are verified.

TinyFish is intentionally excluded.

## Execution model

GitHub file/branch/PR operations are available. Configured GitHub Actions can run CI on their declared events. There is no verified generic workflow-dispatch action or persistent shell in this ChatGPT session. OpenHands mention-to-session creation has been observed, but correlated task completion and artifact retrieval are not yet proven.

## License and provenance

The OpenHands mirror remains source-preserving and retains its source repository attribution. New Blind Sniper runtime files are original integration metadata and contracts. Do not copy third-party implementation code without checking its license and preserving required notices.

## Verification

Run:

```bash
python3 scripts/validate_blind_sniper_runtime.py
python3 -m unittest discover -s tests -p 'test_blind_sniper_runtime.py' -v
```

The GitHub Actions workflow runs both checks for changes to this runtime. Passing registry tests prove the configuration is internally consistent; they do not prove external MCP, OpenHands, browser or background automation end-to-end paths.


## Latest CI verification receipt

- Runtime registry: GitHub Actions run `42473825954`, job `128710593528` — PASS; 6 profiles, 26 agents, 11 adapters, 10 workflows, 10 native skills, 33 OpenHands skills; 3 unit tests OK.
- Native environment: run `42473825834`, job `128710592811` — PASS; 39 required assets, 9 skill contracts, 9 agent contracts, 5 workflows, 6 safe Codex config templates, credential-pattern scan clean.
- Engineering Execution OS compliance: run `42473825927`, job `128710593387` — PASS.

These runs verify the preceding implementation checkpoint. Re-run the workflow after any registry, validator, test or workflow change. They do not prove external adapter end-to-end readiness.
