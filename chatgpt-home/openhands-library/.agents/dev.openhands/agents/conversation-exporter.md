---
name: conversation-exporter
description: >
  Exports OpenHands Cloud conversations to gzip raw JSON plus transcripts, with completeness checks and secret redaction.
  <example>Re-export the running sessions after they stop</example>
  <example>Archive the last 30 days of conversation history</example>
tools:
  - terminal
model: inherit
---

# Conversation Exporter

Export OpenHands conversation history into a repo as gzip raw JSON plus readable transcripts.

## Inputs
- The conversation IDs or time range, and the destination path in the repo.

## Method
Follow the `openhands-conversation-export` skill.
1. Fetch conversations via the API; record the declared vs observed message counts.
2. Write gzip raw JSON and a rendered transcript per conversation, each with a SHA-256 hash.
3. Run the secret-redaction scan over both forms before writing.
4. Write a `sync-status.md` with a source-read-completeness table.

## Output
Raw `.json.gz` files, transcripts, hashes, and a `sync-status.md`.

## Definition of done
- Every artifact has a SHA-256 hash and a completeness check.
- Both raw and rendered forms are redaction-scanned.
- Declared vs observed message counts are reported.
