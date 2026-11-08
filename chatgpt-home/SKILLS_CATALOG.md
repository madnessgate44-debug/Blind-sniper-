# Skills and Agent Library

## Existing OpenHands skill library — verified source
The account-level OpenHands plugin is maintained separately at:
`https://github.com/madnessgate44-debug/Openhands/tree/main/.agents`

Its `AGENTS.md` documents an auto-loaded personal marketplace rooted at `.agents/`, with skills, sub-agents and lifecycle hooks. Its README reports 33 skills, 19 sub-agents and lifecycle hooks. These are OpenHands plugin assets; they are not automatically loaded into ChatGPT merely because this index links to them.

### Skill names found under `.agents/skills/`
- accessibility-audit
- api-design
- arabic-rtl-ui
- architecture-and-adr
- ci-cd-pipelines
- code-review-rubric
- content-vs-brand (path-triggered rule)
- data-privacy-compliance
- database-migrations
- dependency-supply-chain
- docs-evidence-format (path-triggered rule)
- documentation-standards
- early-checkpoint
- engineering-execution-os
- git-workflow
- incident-response
- model-string-hygiene
- multi-session-pr-coordination
- no-schedule-claims (path-triggered rule)
- observability
- openhands-conversation-export
- owner-brief
- owner-policy
- performance-engineering
- prd-authoring
- release-management
- sandbox-lifecycle
- scope-discipline
- secret-redaction-scan
- security-threat-model
- self-driving-loop
- testing-strategy
- zero-cost-gate

## Sub-agents and hooks
- OpenHands repository documents 19 sub-agents under `.agents/dev.openhands/agents/`.
- Lifecycle hooks include tool-use guards and stop/quality/backlog gates; consult the source manifests and hooks before relying on any behavior.
- Validation documented by OpenHands: `python3 scripts/validate.py`, `bash tests/hooks_test.sh`, and `python3 scripts/loader_smoke.py`. These checks have NOT been run by ChatGPT in this session.

## ChatGPT-specific capabilities
- ChatGPT's internal model/system instructions, private runtime skills, and hidden implementation details cannot be exported or copied into GitHub.
- This directory records the user-facing operating contract, durable project memory, and skill references that can be persisted.
- Use connected GitHub tools and any available app/plugin skills when actually present in the active session. Never claim an OpenHands skill is installed in ChatGPT without evidence.

## Synchronization rule
When OpenHands skills or agents change, update this catalog from the live `Openhands` repository and record the source commit or retrieval date.


## Blind Sniper continuity skill — added 2026-11-08
- Path: `chatgpt-home/skills/blind-sniper-continuity/SKILL.md`
- Covers mandatory complete retrieval of all seven continuity files, evidence-tagged incremental GitHub synchronization, and complete historical ChatGPT transcript migration from an authorized account export.
- Includes explicit honesty gates: summaries are not transcripts; no claim of automatic history access or completed migration without source access and reconciliation.


## OpenHands library mirror — imported 2026-11-08
- Destination: `chatgpt-home/openhands-library/`
- Source: `madnessgate44-debug/Openhands` main, tree `ea9f6151e2d1524d8413b1b7994556a7f5495929`.
- Imported 68 source files: 33 skill/rule files, 19 specialist profiles, plugin manifests, hook definitions/scripts, loop/status/backlog docs, validation scripts, tests, workflow, README and AGENTS guidance.
- Blind Sniper's adapted runtime contract: `chatgpt-home/BLIND_SNIPER_OS.md`.
- The mirror is reference material. OpenHands SDK agents/hooks do not automatically execute inside ChatGPT.
