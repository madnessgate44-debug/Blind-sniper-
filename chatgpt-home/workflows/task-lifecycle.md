# Workflow — Task Lifecycle

## States
REQUESTED → INSPECTING → SPECIFIED → PLANNED → DISPATCHED/EXECUTING → VERIFYING → REVIEWING → CLOSED

Terminal alternatives: BLOCKED, CANCELLED, FAILED, OWNER-DECISION.

## Gates
1. **Inspect:** exact source, current state, base SHA and governing policy.
2. **Specify:** numbered requirements, acceptance criteria, non-goals and risk.
3. **Plan:** dependencies, files, worker, permissions, tests and rollback.
4. **Execute:** isolated workspace; smallest complete change; correlated run ID.
5. **Verify:** exact commit/tree, commands, exit codes, raw output and runtime smoke where needed.
6. **Review:** independent review for security, release or high-risk work.
7. **Close:** all evidence persisted; blockers and next action explicit.

## Stop conditions
Unexpected scope, stale branch, missing permission, credential exposure, paid resource, unapproved consequential action, failed critical test, or two attempts without new evidence.

## Closure rule
A task is CLOSED only when every acceptance criterion passes or the Owner explicitly accepts a documented exception. Otherwise use BLOCKED or OWNER-DECISION.
