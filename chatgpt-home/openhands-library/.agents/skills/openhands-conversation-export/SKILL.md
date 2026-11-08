---
name: openhands-conversation-export
description: "This skill should be used when the user asks to \"export conversations\", \"sync OpenHands history\", \"back up conversations\", \"archive transcripts\", or mentions gzip raw JSON, completeness checks, or SHA-256 hashes."
triggers:
- conversation export
- conversation sync
- transcript
- openhands cloud
- conversation history
---

# OpenHands Conversation Export

Reuse this recipe for every export. Never invent counts; report only what the API returns.

## Enumerate conversations
- `GET https://app.all-hands.dev/api/v1/app-conversations/search?limit=100` with header `Authorization: Bearer $OPENHANDS_API_KEY`.
- Follow `next_page_id` until it is null. Cross-check the total with `GET /api/v1/app-conversations/count`.
- Record the page count; if any page is skipped the export is PARTIAL, not complete.

## Pull events per conversation
- `GET /api/v1/conversation/{id}/events/search?limit=100`, follow `next_page_id` to exhaustion.
- Output layout:
  - `raw/openhands-cloud/<id>.events.json.gz` (gzip, plus a SHA-256 per file)
  - `transcripts/openhands-cloud/openhands-<id>.md`

## Completeness grading
- `sandbox_status == PAUSED` -> `VERBATIM_COMPLETE`
- `sandbox_status == RUNNING` -> `VERBATIM_PARTIAL` (re-export after the session stops)
- Always record `declaredMessages`, `observedMessages`, `pages`, `paginationComplete` so a truncated read is visible.

## Async starts
- Create sessions with `POST /api/v1/app-conversations` (async start-task).
- Poll `GET /api/v1/app-conversations/start-tasks?ids=<id>` until state `READY`, then read `app_conversation_id`.

## Redaction (do this before ANY commit)
- GitHub push protection rejects pushes that contain secrets. Redact in BOTH the raw JSON and the readable render.
- Patterns that actually fired: `gAAAAA` (Fernet), `sk-`, `ghp_/gho_/ghu_/github_pat_`, `https://<token>@github.com`, PEM keys, and Gemini keys `AQ.<40+>` and `AIza...`.
- Finish with a sweep over text AND compressed content:
  - `git grep -nE '(gAAAAA|sk-|ghp_|gho_|ghu_|github_pat_|AIza|AQ\.[A-Za-z0-9_-]{40,}|BEGIN [A-Z ]*PRIVATE KEY)' -- .`
  - `find . -name '*.gz' -exec sh -c 'zcat "$1" | grep -nE "gAAAAA|sk-|ghp_|AIza|AQ\.[A-Za-z0-9_-]{40,}" >/dev/null && echo "LEAK: $1"' _ {} \;`

## Rate limits
- Long conversations hit real 429s (100 requests/min). Retry with backoff; if a read still fails, fail loudly (exit 1). Never silently truncate a conversation.

## Scaling note
- Repeated `full_state` / `stats` ConversationStateUpdateEvents dominate raw size. The readable render may summarize them (say so inline); the raw archive must keep everything.
