---
name: agent-dispatch
description: Dispatch bounded work to OpenHands, Forge or specialist agents and close the correlated handoff loop.
triggers: delegate task, ask OpenHands, dispatch Forge, agent handoff, parallel review
risk: medium; high for write/deploy permissions
required_tools: GitHub issue/comment or verified agent API; session/result retrieval
---

# Agent Dispatch Skill

## Purpose
Delegate only when the recipient has a real, verified receive and result path.

## Prerequisites
Read the target agent contract, task ticket and current coordination protocol. Resolve repository, branch, base SHA and permitted scope.

## Permissions
Dispatching a bounded task is allowed. Do not grant broader permissions than the task needs. Merge, deployment, secret changes and paid resources remain Owner-gated.

## Procedure
1. Create a unique task/correlation ID.
2. Define outcome, requirements, acceptance tests, allowed paths, prohibited operations and timeout.
3. Post through the documented channel and record the message/comment ID.
4. Distinguish POSTED, RECEIVED, ACKNOWLEDGED, EXECUTING, RESULT_RETURNED and VERIFIED.
5. Correlate the bot response/session ID to the exact task ID.
6. Retrieve result artifacts: branch, commit, diff, test output, logs and blockers.
7. Independently inspect the diff and evidence.
8. If no correlated result arrives, ask once through the established channel, then mark BLOCKED; do not assume silence means success.
9. Persist the receipt and close the task only after acceptance evidence passes.

## Evidence
Task ID, dispatch ID, receive ID, worker/session ID, repo/branch/commit, artifacts, verification result.

## Failure handling
A generic “I'm on it” response proves receipt/session creation only. It is not task acknowledgment, execution or completion.

## Completion criteria
Correlated result is retrieved, independently verified and written to the durable task record.
