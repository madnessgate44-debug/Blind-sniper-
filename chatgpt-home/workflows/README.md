# Workflow Library

| Workflow | Trigger | Required outputs |
|---|---|---|
| `session-boot.md` | Start/resume Blind Sniper | Seven-file state retrieval, source refresh, capability check |
| `task-lifecycle.md` | New non-trivial task | Inspect → Specify → Plan → Execute → Verify → Review → Close |
| `agent-handoff.md` | External worker delegation | Correlated dispatch, receipt, result and evidence |
| `session-close.md` | Substantive conversation close | Durable checkpoint and next action |
| `release-gate.md` | Release/deployment request | GO/NO-GO, Owner approval and rollback readiness |

Workflow documents are contracts. A workflow is not running unless a real trigger/runner exists and a run is retrieved.
