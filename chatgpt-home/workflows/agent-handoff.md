# Workflow — Agent Handoff

## Task envelope
Task ID, correlation ID, owner, recipient, repository, base SHA, allowed paths, requirements, acceptance tests, forbidden operations, timeout and return format.

## Protocol
1. Confirm recipient channel is currently available.
2. Persist task envelope.
3. Dispatch and record source message/comment ID.
4. Capture actual receipt and session/run ID.
5. Require task-specific acknowledgment, not generic greeting.
6. Retrieve branch, commit, diff, logs and test artifacts.
7. Independently verify result.
8. Persist final receipt and close or block.

## State semantics
POSTED ≠ RECEIVED ≠ ACKNOWLEDGED ≠ EXECUTED ≠ VERIFIED.

## Retry
One bounded follow-up after timeout. Do not create duplicate concurrent workers without idempotency/correlation protection.
