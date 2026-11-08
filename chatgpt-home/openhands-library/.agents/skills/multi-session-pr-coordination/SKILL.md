---
name: multi-session-pr-coordination
description: "This skill should be used when the user asks to \"open a PR\", \"update a PR\", \"merge\", or when multiple OpenHands sessions touch the same repository and duplicate work or clobbered heads are a risk."
triggers:
- pull request
- pr
- concurrent session
- merge
- branch
---

# Multi-Session PR Coordination

Several OpenHands sessions run against the same repo at once. Assume a parallel session may be editing the same branch.

## Before you act
- Enumerate PRs via the GitHub API FIRST (state, head SHA, draft, mergeable).
- Re-fetch immediately before writing: heads move between reads. Never trust a SHA you cached earlier in the session.

## Do not create duplicates
- If an audit/typecheck/review PR already exists, EXTEND it (same branch + updated PR description) with new, distinct findings. Do not open a parallel PR for the same purpose.

## Merge safety
- Never push to `main`. Work on a branch.
- The owner retains merge and deploy. Do not merge unless explicitly told.
- Before merging someone else's PR, independently re-verify the head SHA, not just the description.

## Cadence reality
- No `schedule:` / `cron:` trigger exists in any workflow, and sessions cannot self-schedule. Only checkpoint on invocation.
- Never claim an unattended or scheduled check happened. Verify with `GET actions/runs?event=schedule` before claiming a schedule exists.
