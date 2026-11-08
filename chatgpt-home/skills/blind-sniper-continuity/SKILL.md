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
