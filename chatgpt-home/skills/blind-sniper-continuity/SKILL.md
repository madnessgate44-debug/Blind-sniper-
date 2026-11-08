---
name: blind-sniper-continuity
description: Retrieve Blind Sniper's seven-file GitHub memory, synchronize verified continuity updates, and migrate complete historical ChatGPT transcripts without confusing summaries with raw history.
---

# Blind Sniper Continuity Skill

## Trigger
Use whenever a session starts, the Owner says "resume", asks what was done before, asks to synchronize memory, asks to export/archive conversations, or material project decisions/work are completed.

## Source of truth
Repository: `madnessgate44-debug/Blind-sniper-`
Branch: `main`
Directory: `chatgpt-home/`

## Capability A — retrieve all seven complete files
1. Fetch the full current contents (no line-range truncation) of:
   - `README.md`
   - `OPERATING_PROFILE.md`
   - `MEMORY.md`
   - `PROJECTS.md`
   - `CONVERSATION_CONTINUITY.md`
   - `SKILLS_CATALOG.md`
   - `SYNC_PROTOCOL.md`
2. Verify each fetch returned non-empty content and a blob SHA.
3. Read all content before acting on remembered context.
4. Record retrieval time, branch, each path, SHA, and pass/fail in a checkpoint.
5. If any file fails, mark the checkpoint PARTIAL/BLOCKED and do not claim a complete retrieval.

## Capability B — automatic incremental synchronization
1. After material decisions, completed tasks, verified repository changes, or explicit "sync" requests, update the appropriate continuity file(s).
2. Use evidence labels:
   - `[VERIFIED]`: directly confirmed by a tool/source in this run.
   - `[RECONSTRUCTED]`: summarized from prior context, not raw.
   - `[UNVERIFIED]`: not confirmed.
   - `[BLOCKED]`: could not be performed due to missing access/input.
3. Preserve history. Append dated checkpoints; do not silently erase or rewrite prior decisions.
4. Use GitHub's fetch-before-update SHA workflow. Never perform concurrent writes to the same path.
5. Re-fetch changed files and verify their resulting content and SHAs.
6. Synchronize only what the current execution environment can actually access. A schedule is not proof that connectors, permissions, or raw chat history are available.
7. If the connector cannot write, produce a ready-to-apply patch and state BLOCKED; do not claim success.

## Capability C — full historical transcript migration
**Goal:** migrate the complete user-provided ChatGPT data export, not a memory summary.

1. Obtain an authorized ChatGPT data export (typically the account export archive) from the user or a supported connected source. Do not claim the assistant can silently retrieve account-wide private history without such access.
2. Inventory the archive before transformation. Preserve original files unchanged.
3. Parse every conversation record, retaining stable conversation IDs, message IDs when present, timestamps, role/speaker, message order, content, tool events, and attachment references/metadata available in the export.
4. Store:
   - immutable raw export/archive;
   - normalized per-conversation transcripts;
   - searchable index/manifest;
   - separate reconstructed summaries and project memory.
5. Deduplicate only by stable IDs or exact cryptographic hashes; never merge merely similar conversations.
6. Generate a migration manifest containing archive filename/hash, conversation count, message count, attachment count, parse failures, duplicates, and per-conversation status.
7. Reconcile parsed counts against the export's own inventory where available. Preserve unsupported records and log them as unparsed; do not discard silently.
8. Verify representative transcripts against original raw records and verify all output files/checksums.
9. Declare `MIGRATION COMPLETE` only when all archive entries are accounted for and all discrepancies are explained. Otherwise report `PARTIAL` with exact gaps.
10. Never invent missing timestamps, messages, IDs, or attachment contents. Never represent summaries as verbatim transcripts.

## Checkpoint format
Every run writes a dated checkpoint with:
- identity: Blind Sniper;
- task and run timestamp;
- seven-file retrieval: PASS/PARTIAL plus all seven SHAs;
- sync actions: paths, commit SHAs, verification;
- transcript migration: NOT STARTED / BLOCKED / PARTIAL / COMPLETE with counts and evidence;
- blockers, next action, and responsible actor.

## Safety and scope
- Never commit secrets, credentials, tokens, passwords, or sensitive personal data.
- Do not alter the Miss Noor application or unrelated product files while performing continuity maintenance.
- Respect repository root `AGENTS.md` and `ENGINEERING_EXECUTION_OS.md`.
- Do not claim automatic startup, background execution, transcript access, or successful sync unless verified in the current environment.


## Conversation-close synchronization (primary trigger)
Run this workflow at the end of every substantive conversation, immediately before sending the closing response, whenever the assistant determines the current exchange is complete or the Owner says to stop/end/close it. This replaces a daily timer as the primary sync trigger.

1. Review the current conversation for new decisions, instructions, completed work, verified findings, blockers, and next actions.
2. Fetch the latest versions of the relevant continuity files from GitHub before editing. Do not rely on earlier copies or SHAs.
3. Append a dated closeout entry to the appropriate file(s), with provenance labels and a concise summary. Preserve existing history. Include the conversation-close checkpoint and next-session pickup point.
4. If there are no durable changes, do not create empty commits; still perform the seven-file retrieval check and record a no-change checkpoint only if a meaningful checkpoint file/location is designated.
5. Verify each write by fetching the resulting file and checking its content and SHA. Report exact commits and any failures in the closing response.
6. If GitHub connector access is unavailable, state that closeout sync is BLOCKED; provide the exact pending update in the response. Never claim it ran later in the background.

**Inactivity limitation:** The assistant cannot independently detect that a chat has become inactive, wake itself after the user leaves, or execute a deferred action after the conversation has ended unless a supported external event trigger is actually configured. Therefore, execute closeout synchronously while composing the final response, not after an assumed inactivity timeout. If a session is abandoned without a closing assistant turn, no closeout can be guaranteed.
