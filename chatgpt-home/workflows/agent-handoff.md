# Workflow — Native Model-Agent Execution

## Purpose
Execute a specialist role as a real, separately invoked model run owned by Blind Sniper. Selecting a role contract is not an invocation and does not count as execution.

## Required task envelope
Task ID, agent ID, unique run ID, objective, bounded context references, repository/base SHA where applicable, allowed paths, tool and permission allowlists, acceptance criteria, timeout, retry budget, idempotency key and return schema.

## Protocol
1. Validate task authority, cost boundary, policy and allowed capabilities.
2. Create unique task, agent and run identities.
3. Build fresh bounded context from approved source references; do not reuse another agent's hidden context.
4. Invoke the configured model provider through Blind Sniper's own provider interface.
5. Enforce tool allowlists, permission boundaries, timeout, concurrency and retry limits.
6. Capture the raw model/tool result and correlated run receipt.
7. Verify artifacts, exact repository state, tests and acceptance criteria independently.
8. Persist result/receipt to the approved durable store and close or block the task.

## State semantics
PLANNED ≠ INVOKED ≠ EXECUTED ≠ VERIFIED. A role registry entry or queued task is not proof of an independent model run.

## Failure and retry
Use bounded retries only for classified transient failures. Reuse idempotency keys for replay-safe operations. Never create duplicate concurrent writers. Preserve partial receipts and recover only through the native task ledger.
