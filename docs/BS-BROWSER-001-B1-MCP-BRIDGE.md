# BS-BROWSER-001 — B1 native MCP browser bridge

**Status:** IMPLEMENTED IN SOURCE / NOT TESTED HERE / NOT CONNECTED TO CHATGPT

## Scope

This tranche adds an MCP stdio server inside Blind Sniper. It exposes the existing native browser adapter through five tools:

- `browser.start` — creates a native task record, claims a task lease, transitions it to EXECUTING, and opens the requested URL.
- `browser.action` — dispatches one registered adapter action using internally generated step IDs.
- `browser.status` — returns the current URL, accessibility snapshot, screenshot artifact path and action receipts.
- `browser.resume` — restores a session only when the same private host state and a still-active lease are available.
- `browser.close` — closes the browser and releases the task lease.

Run from a checked-out repository on a host with Python 3.12+, the pinned `agent-browser` CLI, Chromium and the existing browser host policy configured:

```bash
python scripts/blind_sniper_mcp_server.py
```

The process speaks newline-delimited JSON-RPC over stdin/stdout using MCP protocol version `2025-03-26`. It is intended to be registered by an MCP-capable host as a stdio server. It does not open a network listener.

## Host configuration

Required for actual browser execution:

- `BLIND_SNIPER_BROWSER_ALLOWED_DOMAINS` — existing explicit host allowlist; B3 will separately design and test the safe general-public-HTTPS policy.
- `AGENT_BROWSER_BIN` / `AGENT_BROWSER_EXECUTABLE_PATH` — optional existing adapter overrides.
- `BLIND_SNIPER_MCP_STATE_DIR` — persistent private directory outside the public repository.
- `BLIND_SNIPER_MCP_LEDGER` — optional private ledger path, also outside the public repository.
- `BLIND_SNIPER_BROWSER_STATE_DIR` — optional persistent private browser state path, outside the public repository.
- `BLIND_SNIPER_MCP_OWNER_ID` — stable host owner identity; defaults to `blind-sniper-mcp-host`.

Mutating browser actions additionally require both `BLIND_SNIPER_BROWSER_WRITE_APPROVED=1` and `BLIND_SNIPER_BROWSER_APPROVAL_REFERENCE`. These host controls are not set by an MCP request. No credential values are accepted as tool arguments.

## Safety and lifecycle

- Browser actions still pass through `dispatch_browser_action`; the MCP layer does not invoke the adapter directly.
- Task identity, run identity, session identity and step IDs are created internally or validated on resume.
- The native task ledger enforces EXECUTING state, matching implementer, lease ownership, lease duration and idempotent step reservation.
- Browser policy continues to reject non-HTTP(S), embedded URL credentials and destinations outside the host allowlist.
- Existing sensitive selector checks and host approval checks remain active.
- Private task ledger, browser state, screenshots, downloads and receipts are kept outside the public repository.
- CAPTCHA and MFA are user handoffs. The bridge does not bypass them.

## B1 acceptance and known blockers

| Requirement | Acceptance | Current result |
|---|---|---|
| R1 MCP transport | Initialize, list tools, call tools over stdio | Source added; unit tests authored; NOT RUN |
| R2 conversational session interface | Start, action, status, resume, close with internal task/session IDs | Source added; NOT RUN |
| R3 native policy integration | Every action uses the lease-gated dispatcher and existing approval/domain checks | Source review only; runtime NOT RUN |
| R4 structured result | Return URL, page snapshot, screenshot reference and receipts | Source added; runtime NOT RUN |
| R5 ChatGPT invocation | ChatGPT can invoke the MCP server as a callable tool | BLOCKED: current session exposes no custom MCP registration or direct MCP stdio tool |
| R6 live browser E2E | ChatGPT starts a new session and controls an unconfigured site through one conversation | BLOCKED until R5 and a configured browser host are available |

This is a real stdio MCP server implementation, not a live ChatGPT connection. A stdio server requires an MCP host to launch it; a hosted HTTP MCP endpoint requires a persistent browser execution host and a separately verified remote transport. The existing Vercel health function is stateless and cannot itself host the Chromium process. Do not claim B1 passed until the real ChatGPT-to-MCP-to-Chromium loop is exercised.

## Deliberately deferred

- B2 cross-turn/cross-job persistent browser host beyond the local host state/lease recovery implemented here.
- B3 general HTTPS browsing policy, local-network/SSRF containment redesign, authenticated profiles and cookie persistence.
- CAPTCHA/MFA bypass (prohibited).
- Any paid service, paid compute, or external browser/agent runtime.
