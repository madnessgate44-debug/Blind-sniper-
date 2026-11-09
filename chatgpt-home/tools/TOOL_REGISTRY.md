# Blind Sniper Tool and Connector Registry

**Rule:** This registry describes the intended capability model. The active ChatGPT tool inventory is the only authority for what can be called in a given session.

| Tool family | Intended use | Current evidence | State |
|---|---|---|---|
| GitHub connector | Repo/file/branch/issue/PR/Actions operations | Exposed connected GitHub actions | HOST-AVAILABLE |
| Web search/open | Public research and source inspection | Web tool exposed | HOST-AVAILABLE |
| Files | Conversation uploads and Library retrieval | Files actions exposed | HOST-AVAILABLE |
| Python/container | Analysis, file generation and local processing | Runtime tools exposed in supported channels | HOST-AVAILABLE |
| Image generation | Create/edit requested images | ImageGen tool exposed | HOST-AVAILABLE |
| Canva | Design workflows | Connector namespace present; action-specific auth must be checked | HOST-AVAILABLE / VERIFY ACTION |
| Figma | Design files and implementation workflows | Connector namespace present; skill prerequisites apply | HOST-AVAILABLE / VERIFY ACTION |
| Notion | Workspace research/documentation | Connector namespace present; action-specific auth must be checked | HOST-AVAILABLE / VERIFY ACTION |
| OpenHands | Coding worker/session dispatch | GitHub mention route created session IDs; task-specific result retrieval not yet proven | PARTIAL |
| Forge browser MCP | Authenticated browser/computer interaction | Firstborn PR #147 endpoint + PR #148 remote HTTPS smoke/CI; sandbox host is ephemeral; ChatGPT connector not registered | REMOTE-SMOKE-REPORTED / CONNECTOR-BLOCKED |
| Codex CLI | Local terminal, profile and sandbox runtime | No local Codex host exposed to this ChatGPT session | NOT-AVAILABLE-HERE |
| Persistent cloud shell | Isolated terminal/worktree execution | No verified sandbox/session currently established | NOT-ESTABLISHED |
| Brain bridge | Durable agent coordination and callback | GitHub issue #292 available; OpenHands session results returned in correlated comments; direct ChatGPT session API and two consecutive Blind Sniper round trips unproven | PARTIAL |
| Shadow provider pool | Credential health and secure provider allocation | WATCHER.md §14 assigns custody to Shadow; shadow-keys.yml exists; latest reported sweep 0 WORKING / 8 NOT SET | CUSTODIAN-DESIGNATED / POOL-BLOCKED |
| Background automations | Work while chat inactive | Existing team-owned checkpoints; no verified OpenHands receiver | NOT-VERIFIED |

## Tool selection policy
1. Prefer the smallest tool that directly satisfies the task.
2. Discover the exact action schema before invoking a connector.
3. Use a browser tool for UI interaction; web search is not browser control.
4. Never pass secrets through issues, PRs, logs or ordinary files.
5. Verify action results and persist IDs; do not infer success from an attempted call.
6. Recheck availability each session. This registry is a snapshot, not an entitlement guarantee.
