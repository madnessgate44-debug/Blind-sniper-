# Blind Sniper Specialist Agents

Specialists are bounded role contracts. Blind Sniper remains the orchestrator and evidence owner. A role may be executed by the current model, a connected worker, or an external agent only when the relevant runtime exists.

| Agent | Role | Primary deliverable |
|---|---|---|
| `researcher` | Primary-source technical and product research | Cited research brief |
| `planner` | Requirements decomposition and dependency planning | Acceptance map and task DAG |
| `engineer` | Bounded implementation | Branch, commit, diff and test output |
| `reviewer` | Independent correctness/security review | Findings with severity and evidence |
| `qa-verifier` | Test design and runtime acceptance | Verification ledger |
| `recovery` | Diagnose failed/partial runs and restore safe state | Recovery plan and verified checkpoint |
| `watcher` | Monitor explicit queues and report changes | Correlated status digest |
| `shadow` | Adversarial audit and policy/secret review | Blocker-first audit |
| `release-manager` | Release readiness, changelog and rollback assessment | Release gate report |

## Delegation rule
Do not delegate review to the same worker that implemented the change when an independent reviewer is required. Never grant a specialist authority beyond the task envelope.
