# Native Browser Adapter — Implementation Contract

**Task:** BS-20261108-004
**Primary engine:** vercel-labs/agent-browser
**Pinned version:** 0.41.2
**License:** Apache-2.0
**Execution host:** GitHub Actions ubuntu-latest (ephemeral CI host)
**Status:** PARTIAL — two-cycle native-dispatch Chromium E2E, interruption reconciliation, atomic reservation and security hardening passed CI; persistent host remains unverified

## Scope

The adapter in `scripts/blind_sniper_browser.py` invokes the CLI with a fixed argument vector and `shell=False`. It exposes `open`, `snapshot`, `click`, `fill`, `press`, `screenshot`, `get-url`, `close`, `tabs`, `tab-new`, `tab-switch`, `tab-close`, `frame`, `upload`, `download`, and `pdf`. File operations are confined to the adapter upload/artifact workspaces; upload requires explicit host write approval and is limited to 10 MiB and an allowlisted extension; downloads are limited to 25 MiB and PDF/screenshot outputs cannot overwrite existing files.

The native dispatch bridge is `scripts/blind_sniper_browser_dispatch.py`. It is the only supported route from Blind Sniper's native task runtime to browser actions:

```bash
python scripts/blind_sniper_browser_dispatch.py \
  --task-id BS-... --owner-id blind-sniper --run-id run-... \
  --session-id session-... --step-id step-... --action snapshot \
  --action-args-json '[]' --ledger .blind-sniper/state/events.jsonl
```

The bridge:
1. Recovers the authoritative task snapshot from the native append-only ledger.
2. Requires task status `EXECUTING` and an `implementer_id` matching the supplied host owner identity.
3. Requires a current lease owned by that identity with remaining time greater than the browser command timeout plus a 10-second safety margin.
4. Reserves each run/session/step tuple in the canonical ledger before invoking the browser. A previously reserved but incomplete step is blocked for reconciliation; completed steps cannot be replayed.
5. Persists the correlated browser receipt as `BROWSER_ACTION_COMPLETED` after execution. If the lease expires during the bounded action, the receipt is still recorded with `lease_valid_after_action=false`.

The bridge supports both the local `TaskLedger` and the GitHub Contents compare-and-swap ledger configured through the runtime's existing ledger arguments. The owner ID and ledger location are host-supplied; task content cannot grant itself a lease.

## Security and capability limits

- `BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS`: comma-separated allowlist; empty means deny all.
- `BLIND_SNIPER_BROWSER_BLOCKED_DOMAINS`: comma-separated denylist; deny takes precedence.
- `BLIND_SNIPER_BROWSER_WRITE_APPROVED=1` and a non-empty approval reference are required for click/fill/press.
- Browser engine action policy is deny-by-default. Arbitrary JavaScript, cookies, credentials, personal profiles and authentication-state transfer remain disabled. Upload requires host approval and a contained file in the upload workspace; downloads and PDF output are confined to the artifact workspace with size and overwrite limits.
- Page content is untrusted data, never instructions to the operating system or Blind Sniper.
- Agent-browser's domain allowlist is browser-level containment, not an OS firewall. Host/container egress controls remain recommended.

## Correlation, replay and recovery

Each action requires `task_id`, `run_id`, `session_id`, and unique `step_id`. The adapter writes task-scoped session metadata, JSONL receipts and screenshots. The dispatch bridge writes `BROWSER_ACTION_STARTED` before the external action and `BROWSER_ACTION_COMPLETED` with the receipt after it. A started-without-completed record is deliberately not replayed automatically.

The browser daemon itself is not proven recoverable after a GitHub-hosted Actions runner is destroyed. The Oracle Always Free ARM64 self-hosted-runner bootstrap stores browser state under `/var/lib/blind-sniper/browser` and sets the browser daemon idle timeout to `0`, but it has not been provisioned or tested. Cross-job live-session recovery remains pending a real two-job host acceptance run.

## CI boundary

The GitHub Actions workflow installs Node.js 22, `agent-browser@0.41.2`, Chromium and Linux dependencies; it runs browser policy tests, lease-dispatch tests and a real Chromium round trip against a local fixture. The PR branch now includes a zero-recurring-cost Oracle Always Free ARM64 self-hosted-runner bootstrap; provisioning remains owner/account dependent. CI acceptance proves only this ephemeral controlled-fixture path. It does not prove a persistent browser host, authenticated browsing, direct ChatGPT tool invocation or unattended autonomy.


## Additional safety hardening

- URL paths, query strings and fragments are redacted from persisted action receipts, command metadata and session URL state. Only the origin is retained for diagnostics.
- The standalone scripts/blind_sniper_browser.py CLI is disabled so host actions use the native lease-gated dispatcher. The Python adapter class remains an internal implementation component, not a security boundary against arbitrary code running on the host.
- URL redaction and dispatcher-only CLI corrections passed earlier PR-head CI. Extended tabs/frames, upload/download and PDF actions are awaiting the new CI run.


Atomic reservation concurrency, URL redaction and dispatcher-only CLI checks passed on PR-head CI run 42494489650; the full runtime suite passed in run 42494489779. These results do not establish a persistent browser host or cross-job session recovery.


## Native end-to-end acceptance — 2026-11-08

Browser workflow run 42494894841 exercised the actual native dispatch bridge against real Chromium, not a direct adapter-only test.

- Two consecutive cycles completed through EXECUTING task state, an active owner lease, atomic ledger reservation, browser action, and canonical completion receipt.
- Each cycle recorded 8 BROWSER_ACTION_STARTED events, 7 BROWSER_ACTION_COMPLETED events, one BROWSER_ACTION_RECONCILED event and 8 adapter receipts.
- Each cycle executed navigation, accessibility snapshots, screenshot, form fill, submit, post-submit verification and close.
- A simulated interruption occurred after a read-only snapshot and its adapter receipt were persisted but before the ledger completion event.
- Retrying the same run/session/step tuple was rejected before browser adapter construction. The existing receipt was checked, reconciled, and the session then closed using a new step.
- Two cycles produced 16 browser receipts and 25,710 screenshot bytes total. Browser policy tests: 13 PASS; lease-dispatch tests: 8 PASS. The full runtime suite: 76 PASS.
- This proves the bounded local-workspace interruption/reconciliation path. It does not prove a browser daemon or session can survive destruction of the GitHub Actions runner.
