---
name: git-workflow
description: "This skill should be used when the user asks to \"commit\", \"branch\", \"rebase\", \"resolve a conflict\", or mentions conventional commits, force-push safety, or staging changes."
triggers:
- git
- branch
- commit
- rebase
- merge conflict
---

# Git Workflow

- Never push to `main`; work on a branch. The owner retains merge and deploy.
- Conventional, imperative commit subjects; one logical change per commit.
- Pull/rebase before pushing to a shared branch; resolve conflicts deliberately.
- Never force-push a shared branch; never use `--no-verify` to skip hooks.
- Stage deliberately; do not commit build output, secrets, or caches.
