# Workflow Library

The native workflow directory contains nine reusable contracts. The runtime registry contains 17 workflow entries: these nine documented contracts plus six registry-only capability/status records and two additional? See classification below; the registry is authoritative for routing and status.

| Workflow | Trigger | Required outputs |
|---|---|---|
| `session-boot.md` | Start/resume Blind Sniper | Current policy/state retrieval, source refresh and capability check |
| `task-lifecycle.md` | New non-trivial task | Inspect → Specify → Plan → Execute → Verify → Review → Close |
| `agent-handoff.md` | External worker delegation | Correlated dispatch, receipt, result and evidence |
| `session-close.md` | Substantive conversation close | Technical checkpoint and next action; private details stay out of public repo |
| `release-gate.md` | Release/deployment request | GO/NO-GO, Owner approval and rollback readiness |
| `idea-to-contract.md` | Raw idea or new task intake | Outcome, constraints, non-goals and acceptance contract |
| `isolated-execution-line.md` | Explicit multi-station task | Isolated station plan, cumulative gates and human handoff |
| `plugin-and-tool-onboarding.md` | New tool/plugin proposal | Adapter contract, disabled-by-default entry, validation and approval gate |
| `verification-and-handoff.md` | Worker result or task close | Acceptance-to-evidence map, verified result and exact handoff |

## Registry-only workflow entries

These entries intentionally have no standalone markdown contract. Their status and bounded step declarations live in `runtime/workflows.json`.

| Workflow | Classification |
|---|---|
| `research-and-synthesis` | Current-session procedure composed from available web/GitHub research tools; not a background runner |
| `forge-browser-roundtrip` | Blocked capability record; requires a durable browser host and connector registration |
| `persistent-browser-host-acceptance` | Owner-gated acceptance recipe; no persistent host is provisioned |
| `continuous-autonomy` | Capability/status record only; no verified background trigger or runner |
| `conversation-archive-export` | Blocked capability record; no native ChatGPT history-export action is exposed |
| `native-browser-acceptance` | CI-backed browser acceptance record; not evidence of a persistent authenticated browser host |

Workflow documents are contracts. A workflow is not running unless a real trigger/runner exists and a correlated run is retrieved. Registry-only means intentionally represented by registry metadata or CI, not missing or silently executable.
