---
name: ci-cd-pipelines
description: "This skill should be used when the user asks to \"edit the workflow\", \"add a CI gate\", \"fix the pipeline\", \"speed up CI\", or mentions GitHub Actions, build gates, or deployment automation."
triggers:
- ci
- cd
- pipeline
- github actions
- workflow
- gate
---

# CI/CD Pipelines

- Make the typecheck/lint/test/build gate blocking; `continue-on-error: true` hides real failures.
- Pin action versions; cache dependencies by lockfile hash.
- Never print secrets; pass them via the secret store.
- Do not add a `schedule:`/`cron:` trigger or claim a scheduled run without verifying `actions/runs?event=schedule`.
- Fail loudly: a red gate must stop the merge, not warn.
