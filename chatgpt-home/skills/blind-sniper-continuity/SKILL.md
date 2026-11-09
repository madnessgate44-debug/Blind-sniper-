---
name: blind-sniper-continuity
description: Recover Blind Sniper's public technical state, maintain verified technical checkpoints, and handle authorized private-memory or transcript migration without exposing personal data.
triggers: new or resumed session, status recovery, material technical change, authorized transcript migration
risk: high
required_tools: GitHub read access; scoped GitHub branch writes for public technical state; authorized private storage for private data
---

# Blind Sniper Continuity Skill

## Purpose

Maintain continuity for Blind Sniper without treating public repository files as private memory or confusing summaries with raw conversation history.

## Prerequisites

- Read repository-root `AGENTS.md` and `ENGINEERING_EXECUTION_OS.md`.
- Read `chatgpt-home/BLIND_SNIPER.md` and obey its current privacy boundary.
- Resolve the current repository branch, commit and technical state before making changes.
- Before any private-memory or transcript operation, verify the destination repository is private and explicitly authorized.

## Permissions

- Public technical state may be updated only for material technical changes, using an isolated branch and fetch-before-update SHA checks.
- Never read, quote, copy, index or migrate the public copies of `MEMORY.md`, `PROJECTS.md`, `CONVERSATION_CONTINUITY.md` or raw archives as personal context.
- Never write private memory, personal/client details, credentials, raw transcripts or private attachments into the public Blind Sniper repository.
- Private-memory and transcript operations remain BLOCKED until `blind-sniper-private-memory` exists and its private visibility is verified.
- No history rewrite, default-branch push, merge, deployment or permission change without the required current-session authorization.

## Procedure

### A. Technical state recovery

1. Fetch the current branch and HEAD from GitHub; do not assume `main` is active.
2. Read complete technical files from the active branch:
   - `AGENTS.md`
   - `ENGINEERING_EXECUTION_OS.md`
   - `chatgpt-home/BLIND_SNIPER.md`
   - `chatgpt-home/CURRENT_STATE.md`
   - `chatgpt-home/runtime/README.md`
   - `chatgpt-home/runtime/EXECUTION_ENGINE.md`
   - `chatgpt-home/runtime/BUILD_PROGRESS.md`
   - `chatgpt-home/runtime/workflows.json`
   - `chatgpt-home/runtime/profiles.json`
   - `chatgpt-home/runtime/agents.json`
   - `chatgpt-home/runtime/capabilities.json`
3. Verify each fetch is non-empty and record its branch/ref and blob SHA.
4. Reconcile the current-state anchor against actual branches, PRs, commits and workflow runs.
5. If a controlling or required technical file is missing, report PARTIAL/BLOCKED and do not claim complete boot.

### B. Public technical checkpoint

1. After a material technical change, update only the public technical `chatgpt-home/CURRENT_STATE.md` and relevant technical progress records.
2. Record repository, branch, baseline SHA, changed technical paths, verified checks, unverified checks, blockers and next technical action.
3. Do not include personal context, private decisions, client information, raw chat text or private attachments.
4. Fetch-before-update; write one file at a time; re-fetch and verify the resulting content and SHA.
5. Preserve historical evidence and label old CI runs as historical when they do not cover the current commit.
6. Do not create empty commits or claim scheduled/background synchronization.

### C. Authorized private-memory and transcript migration

1. First verify that `blind-sniper-private-memory` exists and is private; until then this capability is BLOCKED.
2. Obtain an authorized ChatGPT data export from the user or a supported connected source.
3. Preserve the original export unchanged in the verified private destination.
4. Normalize conversation records while retaining stable IDs, timestamps, speaker/role, message order, content, tool events and attachment references available in the export.
5. Keep immutable raw export, normalized transcripts, searchable index/manifest and reconstructed summaries separate.
6. Deduplicate only by stable IDs or exact cryptographic hashes.
7. Reconcile parsed conversation/message/attachment counts against the source inventory; log unparsed records and discrepancies.
8. Verify representative transcripts against original records and verify output checksums.
9. Never claim complete migration when any source records remain unaccounted for.
10. Never put raw transcripts or private attachments in the public Blind Sniper repository.

### D. Session close

1. Review the current session for durable technical decisions, verified repository changes, blockers and next technical action.
2. If there is a material public technical change, update the public technical state anchor only.
3. If there is no material technical change, do not create an empty commit.
4. If private storage is unavailable, do not create a public substitute; report private closeout as BLOCKED.
5. Report exact branch, commit, changed paths, verification results and remaining blockers.

## Evidence

For each technical retrieval/write, record the exact path, branch/ref, blob SHA, action, resulting commit SHA and verification outcome. For transcript migration, record source archive hash, parsed counts, discrepancy counts, output hashes and destination privacy evidence. A summary is not a transcript.

## Failure handling

- Missing GitHub access, missing files or stale branch state: stop and report the exact missing evidence.
- Public or unverified private destination: do not read/write private material; mark BLOCKED.
- Partial export, parse failures or mismatched counts: mark PARTIAL and preserve source data.
- Connector write failure: provide a scoped patch only if safe; do not claim synchronization.

## Completion criteria

Technical continuity is complete only when required technical files are retrieved from one corroborated branch and the checkpoint matches actual repository state. Private-memory or transcript migration is complete only when private destination visibility is verified and every source record is accounted for. These are separate completion states.
