# Blind Sniper Specialist Agents

The canonical runtime roster is exactly ten roles. These are bounded role contracts, not proof that ten separate model processes exist. Blind Sniper remains the orchestrator and evidence owner.

| Agent | Role | Primary deliverable |
|---|---|---|
| `blind-sniper` | AI operating lead and dispatcher | Coordinated, authority-compliant task outcome |
| `researcher` | Primary-source technical and product research | Cited research brief |
| `planner` | Requirements decomposition and dependency planning | Acceptance map and task DAG |
| `engineer` | Bounded implementation | Branch, commit, diff and test output |
| `reviewer` | Independent correctness/security review | Findings with severity and evidence |
| `qa-verifier` | Test design and runtime acceptance | Verification ledger |
| `recovery` | Diagnose failed/partial runs and restore safe state | Recovery plan and verified checkpoint |
| `watcher` | Monitor explicit queues and report changes | Correlated status digest |
| `shadow` | Adversarial audit and policy/secret review | Blocker-first audit |
| `release-manager` | Release readiness, changelog and rollback assessment | Release gate report |

## Reference-only profiles — not dispatchable native agents

The following four files are preserved as reusable design patterns. They are deliberately excluded from `agents[]`, all profile allowlists and default routing. Their presence does not create a worker, grant authority or create a separate execution identity.

| Profile | Classification | Reason retained |
|---|---|---|
| `factory-orchestrator.md` | Reference-only | Factory-line/station orchestration pattern; no distinct native routing or profile binding |
| `harness-controller.md` | Reference-only | Overlaps the canonical Blind Sniper controller and planner responsibilities |
| `independent-reviewer.md` | Reference-only | Overlaps reviewer/Shadow; independent identity must be proven by runtime, not a profile label |
| `worker-executor.md` | Reference-only | Bounded worker contract pattern; actual execution remains host-adapter-dependent |

Promote a reference profile only through an explicit architecture decision, a distinct responsibility definition, profile allowlist updates and runtime acceptance. Do not create duplicate roles.

## Delegation rule

Do not delegate review to the same worker that implemented the change when an independent reviewer is required. Never grant a specialist authority beyond the task envelope.
