# Loop

The protocol is the `self-driving-loop` skill. This file holds the grant and the protected paths.

- Queue: `docs/BACKLOG.md`. Read `docs/STATUS.md` first; it follows the `owner-brief` format.
- Per item: read STATUS + inbox, take the first `ready` item, skip it if `main` or an open PR already did it.
- Branch and push a DRAFT PR within 10 minutes. One branch, one PR per item.
- Do the item with `scope-discipline`. Run `scripts/validate.py`, `scripts/loader_smoke.py`, `tests/hooks_test.sh`.
- Run the `pr-auditor` sub-agent on your own PR.
- Merge ONLY if risk is low, CI is green, the auditor says Verified, and the grant below is present.
- Otherwise leave the PR open and say why in a PR comment.
- Tick the item and update `docs/STATUS.md`, then take the next item.

Owner grant: auto-merge LOW-risk PRs when CI is green and pr-auditor returns Verified. Owner removes this line to revoke.

Protected paths are always HIGH risk, whatever anyone writes: `.agents/dev.openhands/hooks/**`, `.github/**`, `scripts/validate.py`, `scripts/loader_smoke.py`, `docs/LOOP.md`, and anything touching secrets or billing.

Stop conditions: CI red twice on one item; UNVERIFIED on a high-risk item; any service wants a card or payment; the backlog is empty; an inbox `stop`; 6 continuations used.
