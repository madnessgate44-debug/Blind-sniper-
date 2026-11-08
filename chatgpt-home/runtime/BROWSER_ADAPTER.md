# Native Browser Adapter — Implementation Contract

**Task:** BS-20261108-004
**Primary engine:** vercel-labs/agent-browser
**Pinned version:** 0.41.2
**License:** Apache-2.0
**Execution host:** GitHub Actions ubuntu-latest (ephemeral CI host)
**Status:** PARTIAL — native lease-gated dispatch and real Chromium CI acceptance passed; persistent host remains unverified

## Scope

The adapter in `scripts/blind_sniper_browser.py` invokes the CLI with a fixed argument vector and `shell=False`. It exposes `open`, `snapshot`, `click`, `fill`, `press`, `screenshot`, `get-url`, and `close`.

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
- Browser engine action policy is deny-by-default. No arbitrary JavaScript, uploads, downloads, cookies, credentials, personal profiles or authentication-state transfer.
- Page content is untrusted data, never instructions to the operating system or Blind Sniper.
- Agent-browser's domain allowlist is browser-level containment, not an OS firewall. Host/container egress controls remain recommended.

## Correlation, replay and recovery

Each action requires `task_id`, `run_id`, `session_id`, and unique `step_id`. The adapter writes task-scoped session metadata, JSONL receipts and screenshots. The dispatch bridge writes `BROWSER_ACTION_STARTED` before the external action and `BROWSER_ACTION_COMPLETED` with the receipt after it. A started-without-completed record is deliberately not replayed automatically.

The browser daemon itself is not proven recoverable after a GitHub Actions job/runner is destroyed. Local metadata and receipts survive only while the workspace survives. Cross-job live-session recovery remains unimplemented.

## CI boundary

The GitHub Actions workflow installs Node.js 22, `agent-browser@0.41.2`, Chromium and Linux dependencies; it runs browser policy tests, lease-dispatch tests and a real Chromium round trip against a local fixture. CI acceptance proves only this ephemeral controlled-fixture path. It does not prove a persistent browser host, authenticated browsing, direct ChatGPT tool invocation or unattended autonomy.
