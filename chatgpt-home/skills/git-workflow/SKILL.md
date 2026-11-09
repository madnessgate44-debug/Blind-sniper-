---
name: git-workflow
description: Commit, branch, rebase, resolve conflicts and push safely under the active standing Owner delegation.
triggers: commit, branch, rebase, conflict, push, stage, conventional commit
risk: medium; high for default-branch pushes, merge and history rewrite
required_tools: git; GitHub connector; the active standing delegation record
---

# Git Workflow

## Purpose
Make deliberate, reversible, evidence-backed version-control changes under the active standing Owner delegation.

## Prerequisites
Read `chatgpt-home/AUTHORITY_DELEGATION.md`. Confirm the delegation is active and covers the intended repository and action. Establish the current branch and commit before changing anything.

## Permissions
Within `madnessgate44-debug/Blind-sniper-`, the delegation covers branch and default-branch pushes, merges, and CI/workflow edits without repeat approval. Force-push, history rewrite, branch deletion and changes to other repositories are excluded.

## Procedure
1. Work on a branch. Conventional, imperative commit subjects; one logical change per commit.
2. Pull/rebase before pushing to a shared branch; resolve conflicts deliberately, preserving unrelated work.
3. Never force-push a shared branch; never use `--no-verify` to skip hooks.
4. Stage deliberately; do not commit build output, secrets, or caches.
5. Fast-forward shared-branch updates when the remote head still equals your parent; otherwise stop and reconcile rather than overwrite.
6. A direct default-branch change is permitted only when it is the smallest appropriate route for canonical policy, urgent repairs or a completed release.

## Evidence
Record the base commit, head commit, branch name, the push result the host confirms, and the files changed.

## Failure handling
On a non-fast-forward or unexpected remote head, stop and re-inspect before acting. On conflict, resolve explicitly; do not discard others' work.

## Completion criteria
The host confirms the push/merge; the recorded SHA matches the host state; no excluded action was performed.
