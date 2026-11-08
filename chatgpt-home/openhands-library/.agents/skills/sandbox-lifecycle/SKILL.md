---
name: sandbox-lifecycle
description: "This skill should be used when the served app returns 502, the sandbox restarted, ports stopped responding, or build and serve tooling vanished from a session."
triggers:
- sandbox
- restart
- port
- "502"
- serve
---

# Sandbox Lifecycle

## What a restart wipes
- `/tmp` (QA directories, playwright, the served process) is wiped and the public URL 502s.
- `dist/` survives.

## Restart the served app
```bash
PORT=12000 NODE_ENV=production nohup node ./node_modules/.bin/tsx server.ts &
```
- Port 12000 -> work-1 URL, port 12001 -> work-2.
- Reinstall `playwright-core` with `--no-save` after a restart.

## Pre-test hygiene
- The `run_check` test runs `git diff --check` in the repo, so a trailing blank line at EOF in any edited file FAILS that test. Strip them before `npm test`:
  ```bash
  perl -0pi -e 's/\n+\z/\n/' <files>
  ```
- `npm test` skips live tests when `OPENHANDS_API_KEY` is unset (3 skipped). The live suite is slow (~6 min).
