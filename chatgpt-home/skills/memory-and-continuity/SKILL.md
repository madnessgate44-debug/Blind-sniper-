---
name: memory-and-continuity
description: Recover and persist task-relevant state, decisions, transcripts and evidence without fabricating continuity.
triggers: resume, session start, remember, prior conversation, project checkpoint, session close
risk: medium
required_tools: GitHub file retrieval/write; source export connector for raw transcript migration
---

# Memory and Continuity Skill

## Purpose
Maintain durable, provenance-aware state across conversations and workers.

## Prerequisites
Load the seven required continuity files and the task's live source of truth. Identify which information is verified, reconstructed or unknown.

## Permissions
Read and update task-relevant continuity files on the authorized branch. Do not store credentials, secrets or unnecessary sensitive personal information.

## Procedure
1. Retrieve complete required files and record blob SHAs.
2. Reconcile current GitHub state before relying on older notes.
3. Preserve raw source artifacts separately from summaries.
4. Append decisions, artifacts, evidence, status and next action.
5. Label facts [VERIFIED], [REPORTED], [INFERENCE], [RECONSTRUCTED], [UNKNOWN] or [BLOCKED].
6. Keep a stable task/run correlation ID.
7. Re-fetch each updated file to verify the write.
8. At conversation close, synchronize material outcomes and unresolved blockers.
9. For transcript migration, require an actual authorized export; reconcile counts and checksums.

## Evidence
Source IDs, timestamps, file paths, blob SHAs, conversation/export coverage and checksums where available.

## Failure handling
If a required file or source cannot be retrieved, record the exact failure and do not fabricate missing history.

## Completion criteria
State is recoverable, provenance is clear, history is preserved and every write is verified.
