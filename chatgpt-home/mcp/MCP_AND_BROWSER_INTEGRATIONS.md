# MCP, Browser and External Tool Integrations

## Integration contract
Every server/connector entry must document: provider, transport, endpoint, authentication method, enabled tools, disabled tools, tool-level approval, timeout, data boundary, cost class, health check, owner and rollback.

## Current integrations

| Integration | Intended capability | Configuration state | Runtime state |
|---|---|---|---|
| GitHub connector | Repository, issue, PR and Actions API | Connected in ChatGPT | HOST-AVAILABLE |
| Web search | Public web research | Platform tool | HOST-AVAILABLE; not interactive browser control |
| Forge HTTP MCP | Browser/computer interaction through Firstborn | PR #147; public HTTPS deployment and ChatGPT connector registration remain open | BLOCKED in this session |
| OpenHands | Coding execution and specialist agents | GitHub App mention route creates sessions | PARTIAL; task-result retrieval not proven |
| Brain | Durable coordination and handoff | GitHub issue #292 and PR #298 routing fix proposed | PARTIAL; do not treat draft PR as merged |
| Codex MCP | Future host integration | No Codex host loaded here | NOT CONFIGURED |

## Forge server activation gate
Do not enable until all are true:
1. Public HTTPS endpoint is deployed at a verified URL.
2. Authentication is configured through an approved secret store; no token is committed or pasted into chat.
3. Tool allowlist is minimal and read-only by default where possible.
4. Tool-level approval protects submissions, account changes, purchases and destructive actions.
5. Unauthorized/no-token request returns 401; authorized health/initialize call succeeds.
6. ChatGPT connector registration is completed by an authorized UI/API route.
7. A harmless browser round trip returns a correlated result and audit record.
8. OpenHands can call the same approved route if that is part of the acceptance scope.

## Browser vs web distinction
Web search/open can retrieve public pages. It cannot sign in, click controls, fill forms or inspect authenticated UI. Those require a browser/computer-use tool actually exposed to the current session.
