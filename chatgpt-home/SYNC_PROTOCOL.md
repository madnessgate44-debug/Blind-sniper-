# Blind Sniper Continuity and Synchronization Protocol

## Purpose
Blind Sniper must retrieve all seven complete continuity files at every available session start, compare fetched blob SHAs against the previous checkpoint, and refresh the continuity record after material decisions or completed work.
Keep ChatGPT's project context recoverable across conversations without pretending that this repository can automatically read every ChatGPT chat.

## Session start
1. Read root `AGENTS.md` and `ENGINEERING_EXECUTION_OS.md`.
2. Read this directory's README, operating profile, memory, project map, continuity notes and skill catalog.
3. Refresh live GitHub state for the task's relevant repositories, issues, PRs, workflows and coordination records.
4. Check Brain issue #292 and the latest OpenHands status/handoff when the task concerns the five-product coordination scope.
5. Reconcile differences. Current source evidence outranks stale memory. Preserve uncertainty rather than silently resolving contradictions.

## Session close
Append a dated continuity entry containing:
- user intent and scope;
- decisions and approvals;
- artifacts created/updated with exact repository paths;
- evidence refs (issue, PR, commit, workflow run, file);
- status using REQUESTED / STARTED / COMPLETED / VERIFIED / MERGED / DEPLOYED / BLOCKED / UNKNOWN;
- blockers and next action.

Never store raw credentials, tokens, personal secrets, or unnecessary sensitive conversation content.

## Transcript archival
- Raw conversation export and a reconstructed summary are different artifacts. Label each clearly.
- For every actual export, record source conversation identifier if available, export timestamp, coverage start/end, completeness, redaction status, and checksum.
- Never fabricate missing messages, tool calls, attachments, or timestamps.
- Incremental export must use a durable cursor/watermark and demonstrate a successful end-to-end run.
- A successful GitHub file write is not proof that automatic ChatGPT conversation export is configured.
- If the active ChatGPT environment does not expose a complete conversation-export API or connector, state BLOCKED for raw automatic export and retain only explicit user-provided/retrieved summaries until a real integration is implemented.

## Two-way coordination
- Use Brain's documented MCP/tools only after authentication is established.
- Record each request and response with correlation ID, timestamp, actor, status, and evidence.
- HTTP 401 without credentials is not a successful connection; do not ask the Owner to paste secrets. Route credential-pool readiness to Shadow through the authorized secret-management workflow.
- Never treat silence as agreement or as task completion.
- A round trip is VERIFIED only after ChatGPT sends a real request, receives the correlated response, and persists the evidence.

## Change discipline
- Prefer append-only continuity records.
- For updates, inspect existing content and preserve history.
- Do not alter the Miss Noor app, its deployment, or root policy as part of memory maintenance.
- Do not change secrets, workflows, protected paths, merge state or deployment state without the root OS authorization.


## Three mandatory capabilities
1. **Seven-file retrieval:** Fetch the complete current contents of README, OPERATING_PROFILE, MEMORY, PROJECTS, CONVERSATION_CONTINUITY, SKILLS_CATALOG, and SYNC_PROTOCOL from the default branch. Verify all seven; partial retrieval is a failed checkpoint.
2. **Incremental synchronization:** After material work, append a dated, provenance-tagged update to the relevant continuity file; preserve prior facts, distinguish VERIFIED / RECONSTRUCTED / UNVERIFIED, and commit through GitHub. Never overwrite raw transcripts with summaries.
3. **Historical transcript migration:** Import the user's complete ChatGPT data export when supplied or when an authorized export source becomes available. Inventory every conversation, preserve original message order, timestamps, roles, attachments/metadata where available, deduplicate by stable conversation/message IDs, and store raw exports separately from searchable indexes and summaries. Produce counts, gaps, checksums, and a migration manifest. Do not claim complete migration until counts reconcile against the export manifest.

## Hard limitations and honesty gates
- A GitHub connector does not itself grant access to the user's complete ChatGPT account history.
- A reconstructed memory summary is not a transcript. Never label it complete, verbatim, or migrated.
- Scheduled synchronization can only use sources and connectors actually available to that run. If GitHub or transcript export access is absent, report BLOCKED with the missing permission/input; do not fabricate a successful sync.
- Never store secrets, access tokens, passwords, or sensitive personal data in the repository.


## Conversation-close trigger
The primary synchronization trigger is the end of each substantive conversation, immediately before Blind Sniper sends its closing response. Review the current exchange, append verified continuity updates, verify GitHub writes, and report the checkpoint. Do not wait for a daily schedule. Inactivity itself is not observable by the assistant; no post-session background execution is implied. If no closing assistant turn occurs, sync cannot be guaranteed.
