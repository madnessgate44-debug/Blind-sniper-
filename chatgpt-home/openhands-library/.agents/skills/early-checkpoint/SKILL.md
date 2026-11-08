---
name: early-checkpoint
description: "This skill should be used when starting any multi-step task, when a task will take more than a few minutes, or after a sandbox restart, and whenever work exists only locally."
triggers:
- start task
- checkpoint
- sandbox restart
- draft pr
- resume
- lost work
---

# Early Checkpoint

Sandbox restarts wipe `/tmp` and uncommitted work. Unpushed work does not exist.

- Within the first 10 minutes: clone, branch from `main` as `<type>/<short-name>`, commit one real file (even a plan stub), push, open a DRAFT PR.
- Push after every logical unit, and at least every ~15 minutes of work.
- Work inside the repo checkout. Keep scratch scripts in the repo (`scripts/` or `tests/`) or push them.
- Never push to `main`. Never merge. The owner merges.
- The PR body holds a checklist. Update it as you go; the final report goes at the top of the body.
- After a restart: re-clone, `git fetch`, resume from the last pushed branch, and say in one line what was lost.
- If blocked, push what exists with a `BLOCKED` section naming the reason. Do not sit idle.
- Related: `sandbox-lifecycle`, `multi-session-pr-coordination`.
