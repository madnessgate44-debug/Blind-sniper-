# Native Browser Adapter — Implementation Contract

**Task:** BS-20261108-004
**Primary engine:** vercel-labs/agent-browser
**Pinned version:** 0.41.2
**License:** Apache-2.0
**Execution host:** GitHub Actions ubuntu-latest (ephemeral CI host)
**Status:** PARTIAL — implementation and real Chromium CI acceptance passed; persistent host and advanced capabilities remain open

## Scope in the first implementation slice

The adapter in `scripts/blind_sniper_browser.py` invokes the CLI with a fixed argument vector and `shell=False`. It exposes:

- `open`: navigate to an allowlisted HTTP(S) URL.
- `snapshot`: retrieve the accessibility/page snapshot.
- `click`, `fill`, `press`: mutating actions requiring host write approval.
- `screenshot`: capture an image inside the adapter artifact directory.
- `get-url`: inspect the current URL.
- `close`: close the task-scoped browser session.

The initial slice intentionally does not expose uploads/downloads, tabs/frames, PDF, cookies, authentication state, arbitrary JavaScript, remote browser providers or personal browser profiles.

## Host configuration

Required host environment:
- `BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS`: comma-separated allowlist. Empty means deny all.
- `BLIND_SNIPER_BROWSER_BLOCKED_DOMAINS`: comma-separated denylist. Deny takes precedence.
- `BLIND_SNIPER_BROWSER_WRITE_APPROVED=1` and a non-empty approval reference for click/fill/press.

The CI workflow permits writes only against a local fixture served on loopback. A production host must source approvals from its trusted owner/approval mechanism; an environment variable is only a host attestation and does not cryptographically authenticate the approver.

## Correlation and evidence

Every action requires `task_id`, `run_id`, `session_id`, and unique `step_id`. The adapter writes:
- task-scoped session metadata under `.blind-sniper/browser/sessions/`;
- JSONL action receipts under `.blind-sniper/browser/receipts/`;
- screenshots under `.blind-sniper/browser/artifacts/`.

Receipts contain timestamps, requested/observed URL, action, sanitized command metadata, exit status, output hashes and artifact paths. Page content is returned to the caller but is not stored in receipts.

The adapter refuses duplicate step IDs before issuing the command and rejects session reuse across different task/run identities. A redirected or mutated page URL is checked against host policy; an out-of-policy destination causes session closure and a failed receipt.

## Recovery and persistence

Session metadata and receipts survive process restarts only while the same workspace remains available. GitHub Actions destroys its runner after the job. The actual browser daemon and live page state are therefore not proven recoverable across job interruption. Cross-job authenticated continuity is explicitly out of scope.

## Reproducible CI host

`.github/workflows/blind-sniper-browser.yml`:
1. provisions `ubuntu-latest`;
2. installs Python 3.12 and Node.js 22;
3. installs `agent-browser@0.41.2`;
4. installs Chrome for Testing and Linux dependencies with `agent-browser install --with-deps`;
5. runs policy unit tests;
6. runs a real Chromium round trip against a local fixture;
7. uploads short-retention receipts and screenshots.

This proves only the CI-hosted fixture path if and when the workflow passes. It does not prove direct ChatGPT browser invocation, persistent hosting, authenticated browsing, or general-purpose unattended automation.

## Security boundaries

- Web page content is untrusted data, never instructions to the operating system or Blind Sniper.
- No credentials, cookies, private profiles or auth-state files are imported or persisted.
- HTTP(S) only; host allowlist required; denylist wins.
- Mutating browser actions are blocked unless host approval is supplied.
- No purchases, payments, external messages, account changes, destructive operations or credential entry.
- No paid browser provider is required.
