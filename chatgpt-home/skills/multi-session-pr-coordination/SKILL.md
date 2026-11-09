---
name: multi-session-pr-coordination
description: Coordinate pull requests safely when more than one session or worker may touch the same repository.
triggers: open a PR, update a PR, merge, concurrent sessions, duplicate work, clobbered head
risk: medium; high for merges and default-branch pushes
required_tools: GitHub connector; the active standing delegation record
---

# Multi-Session PR Coordination

## Purpose
Avoid duplicate work and clobbered branch heads when multiple sessions or workers touch the same repository, while using the active standing Owner delegation.

## Prerequisites
Read `chatgpt-home/AUTHORITY_DELEGATION.md`. Confirm the delegation covers the exact repository and action. Read live PR state before writing.

## Permissions
Within `madnessgate44-debug/Blind-sniper-`, the delegation covers PR creation, update, closure and merges without repeat approval. Force-push, history rewrite, branch deletion and other repositories are excluded.

## Procedure
1. Work on a branch and push a DRAFT PR within the first 10 minutes; one branch, one PR per item.
2. Re-read the live PR head before every push. If the remote head no longer equals your parent, stop and reconcile instead of overwriting.
3. Never force-push a shared branch. Fast-forward only.
4. Before opening a new PR, check `main` and open PRs; skip work already done.
5. Record the base, head and mergeability state you observed; verify the resulting GitHub state after acting.
6. When multiple PRs overlap, preserve unrelated work and state the merge ordering explicitly.

## Evidence
The live PR number, head SHA, base, mergeable state, review state and the confirmed result of each write.

## Failure handling
On a clobbered or diverged head, stop and report the exact state; do not silently rebase over another session's work. On a merge conflict, reconcile deliberately or leave the PR open with a comment.

## Completion criteria
The host confirms each action; no duplicate PR was created; no other session's work was overwritten.
