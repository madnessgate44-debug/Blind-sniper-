---
name: github-workspace
description: Inspect and operate GitHub repositories, branches, files, issues, pull requests and Actions with evidence-first discipline.
triggers: repository task, code change, issue, pull request, branch, GitHub Actions, repo audit
risk: medium; high for protected branches, secrets, merge, release or deployment
required_tools: GitHub connector; workflow runner for execution tests
---

# GitHub Workspace Skill

## Purpose
Perform repository work directly through authorized GitHub tools without asking the Owner to do routine retrieval or edits.

## Prerequisites
- Resolve exact owner/repository, branch and task scope.
- Read root `AGENTS.md` and `ENGINEERING_EXECUTION_OS.md` when present.
- Inspect current branch head, working PRs, relevant files and recent workflow state.
- Establish baseline commit and preserve unrelated changes.

## Permissions
- Read operations: allowed for task-relevant repositories.
- File writes: only on a task-scoped branch and within authorized paths.
- Issues/comments: allowed for task coordination when the user requests execution.
- Merge, release, deployment and CI/CD changes: allowed without repeat approval only when covered by the active standing delegation for `madnessgate44-debug/Blind-sniper-`. Secret/credential mutation or disclosure, account/repository permission changes, history rewrite, paid spend and private-data publication remain excluded.

## Procedure
1. Inspect repository metadata, branch and exact target files.
2. Fetch complete relevant file contents and blob SHAs.
3. Convert request into numbered requirements and acceptance criteria.
4. Choose the smallest bounded change; avoid unrelated cleanup.
5. Prefer a task branch and PR. A direct default-branch push is permitted for this repository under the standing delegation when it is the smallest appropriate route; inspect the target SHA first.
6. Write files sequentially. For updates, use the current blob SHA; re-fetch after each write to verify.
7. Inspect the resulting diff and commit.
8. Inspect workflow runs associated with the exact commit; inspect jobs and steps, not only top-level status.
9. If runtime behavior matters, require a live smoke test; CI green alone is insufficient.
10. Record PR, commit, test evidence, unresolved gates and next action.

## Evidence
Record repository, branch, base SHA, changed paths, commit SHA, PR URL, workflow run IDs, job/step results and exact runtime observations.

## Failure handling
Stop on branch drift, stale blob SHA, permission failure, unexpected file content or failing checks. Re-fetch and reconcile; never force-write over unknown changes.

## Completion criteria
All acceptance criteria have direct evidence, diff is inspected, checks are tied to exact SHA, and the persistent task record is updated. A created PR is not automatically verified or merged.
