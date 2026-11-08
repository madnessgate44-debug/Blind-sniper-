---
name: no-schedule-claims
description: "Applies to workflow and YAML files. Do not add a schedule or cron trigger, or claim a scheduled run, without evidence."
paths:
  - '.github/workflows/**'
  - '**/*.yml'
  - '**/*.yaml'
---

WORKFLOW RULE: Do not add a `schedule:` or `cron:` trigger, and do not claim a scheduled run exists, without evidence.

- To claim a schedule is active, verify with `GET /repos/{owner}/{repo}/actions/runs?event=schedule` and quote the run count. A workflow file on a non-default branch does not run.
- A written cadence in docs is NOT a scheduler. Say so explicitly.
- State clearly that sessions cannot self-schedule and only checkpoint on invocation.
