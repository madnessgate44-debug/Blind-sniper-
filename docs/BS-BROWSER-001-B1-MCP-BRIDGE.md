# BS-BROWSER-001 — native MCP browser bridge

**Status:** Live native browser workflow and sandbox snapshot/resume verified; ChatGPT invocation remains BLOCKED. B1 is not accepted.

## MCP interface

The native stdio server is `scripts/blind_sniper_mcp_server.py`. It speaks newline-delimited JSON-RPC using MCP protocol `2025-03-26` and exposes six tools:

- `browser.start` — creates a native task/run/session, claims the task lease, transitions to EXECUTING and opens the initial URL.
- `browser.action` — dispatches one registered browser action through `dispatch_browser_action` with an internally generated step ID.
- `browser.status` — returns URL, title, accessibility snapshot, screenshot reference and action receipts.
- `browser.detach` — closes the browser process while preserving the resumable session/profile and task lease.
- `browser.resume` — restores the private profile and saved URL; atomically renews or reclaims the lease for the same native owner only while the task remains EXECUTING.
- `browser.close` — closes the browser and releases the task lease.

Run on a host with Python 3.12+, the pinned `agent-browser` CLI, Chromium and the host browser policy:

```bash
python scripts/blind_sniper_mcp_server.py
```

The stdio process does not expose a network listener. An MCP-capable host must launch and register it. The current ChatGPT session still has no direct stdio registration/invocation action.

## Host configuration

- `BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS` — explicit host allowlist when general HTTPS mode is disabled.
- `BLIND_SNIPER_BROWSER_GENERAL_HTTPS=1` — enables public HTTPS destinations after host/IP policy checks; do not treat this flag alone as a completed B3 security review.
- `BLIND_SNIPER_BROWSER_REQUIRE_IPV6_DISABLE=1` — requires host IPv6 egress disablement before general browsing.
- `BLIND_SNIPER_BROWSER_PERSISTENT_PROFILE=1` — enables a private browser profile and agent-browser autosave/restore state.
- `BLIND_SNIPER_MCP_STATE_DIR`, `BLIND_SNIPER_MCP_LEDGER` and `BLIND_SNIPER_BROWSER_STATE_DIR` — private persistent paths outside the public repository.
- `BLIND_SNIPER_MCP_OWNER_ID` — stable host owner identity; defaults to `blind-sniper-mcp-host`.
- Mutating actions require host-set `BLIND_SNIPER_BROWSER_WRITE_APPROVED=1` and `BLIND_SNIPER_BROWSER_APPROVAL_REFERENCE`; MCP request arguments cannot grant this approval.

## Safety and lifecycle

- Every action remains lease-gated through `dispatch_browser_action`; MCP does not call the adapter directly.
- Task/run/session/step identities are generated internally or validated on resume.
- Resume only accepts an EXECUTING task and attempts an atomic lease claim/renewal for the configured native owner. A closed/terminal task is not revived.
- URL validation rejects non-HTTP(S), embedded URL credentials, local/non-public hostnames and non-global IP resolutions. The host must verify IPv6 egress controls for general browsing.
- Sensitive form fields remain blocked; form writes require host approval. The test form below was filled but deliberately not submitted.
- Ledger, browser profile, screenshots, downloads and receipts remain outside the public repository.
- CAPTCHA/MFA are user handoffs; the browser does not bypass them.

## Live verification — 2026-11-14

**Native MCP/Chromium workflow:** A JSON-RPC test harness launched the real MCP stdio process inside a named Vercel sandbox and exercised it against public websites:

1. Opened an unfamiliar MDN search-results page for `browser automation` and captured its accessibility snapshot.
2. Selected page text and invoked `clipboard-copy`; action receipt exit code was 0. Browser permission policy denied clipboard read-back, so clipboard contents were not independently verified.
3. Filled `custname` and `comments` on `https://httpbin.org/forms/post`; both fill receipts exit code 0; form was not submitted.
4. Downloaded the sample HTML file from `https://freetoolsforweb.com/sample-files/documents/html`; download receipt exit code 0, 3,624 bytes, SHA-256 `302b7f0b3f441ea2c56a47dd2233a01f7cf12ce2785d75908a3a22173f750fa5`.
5. Called `browser.detach`, snapshotted the named sandbox, resumed it in a new sandbox session, and called `browser.resume` with the same task/run/session IDs. `browser.status` returned the same final URL and title; the downloaded file remained present; `browser.close` returned `lease_released=true`.

**Separate cookie test:** A test cookie set by `httpbin.org` survived detach → sandbox snapshot → new sandbox session → resume. This proves test-cookie persistence, not a logged-in user profile or authenticated account workflow.

**Verification commands and results:**

- `python -m unittest discover -s tests -v` → exit 0; 287 tests; `OK`.
- `python -m unittest discover -s tests -p 'test_blind_sniper_browser.py' -v` → 40 tests; `OK`.
- `python -m unittest discover -s tests -p 'test_blind_sniper_browser_dispatch.py' -v` → 9 tests; `OK`.
- `python -m unittest discover -s tests -p 'test_blind_sniper_mcp_server.py' -v` → 17 tests; `OK`.
- `python scripts/validate_blind_sniper_runtime.py` → registry cross-references and safety invariants PASS.
- `python scripts/validate_codex_config.py` → six Codex config templates PASS.
- `python -m py_compile scripts/blind_sniper_browser.py scripts/blind_sniper_mcp_server.py` → exit 0.
- `git diff --check` → exit 0.

## Acceptance status and remaining blockers

| Requirement | Evidence | Status |
|---|---|---|
| Native MCP protocol and tool dispatch | Live stdio JSON-RPC initialize/tool calls plus 17 MCP unit tests | [V] Runtime verified |
| Browser open/search/copy/fill/download | Live Chromium receipts; clipboard copy command passed, read-back denied | [V] Workflow actions verified with clipboard read-back limitation |
| Detach/restart/resume | Same task/run/session IDs and final page restored after sandbox snapshot/resume | [V] Snapshot/resume verified |
| ChatGPT direct invocation | No custom MCP stdio registration/invocation tool is exposed in this ChatGPT session | [B] B1 acceptance blocked |
| Persistent production host and zero-cost eligibility | Vercel sandbox snapshot works; host lifetime, billing and no-card eligibility not independently verified | [U] Not accepted as a permanent free host |
| General browsing security and authenticated profiles | Public HTTPS was exercised with host controls; redirect/SSRF/DNS-rebinding review and authenticated-profile workflow remain unverified | [B] B3 not complete |

The live browser workflow above was driven by a test harness inside the sandbox, **not by ChatGPT invoking Blind Sniper directly**. Do not mark B1 complete until the real ChatGPT-to-MCP-to-Chromium path works in one conversation. Do not mark B2 as a permanent host until zero-cost eligibility, retention and restart behavior are verified. Do not mark B3 complete until redirect/SSRF controls and authenticated-profile handling pass adversarial tests.
