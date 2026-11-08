# Workflow — Session Boot

## Entry
A new conversation, resume request, or instruction to operate as Blind Sniper.

## Sequence
1. Load root `AGENTS.md` and `ENGINEERING_EXECUTION_OS.md`.
2. Load Blind Sniper entrypoint, operating profile, memory, project map, continuity, skill catalog and sync protocol.
3. Record exact blob SHAs and retrieval time.
4. Read the environment manifest and tool registry.
5. Discover relevant installed plugin skills before calling tools that require them.
6. Refresh live state for the active task: repository, branch, issue/PR, workflow and agent replies.
7. Select execution mode: Native, Portable or Audited.
8. Report only material conflicts/blockers; do not repeat already-known context.

## Failure states
- Any mandatory file unavailable: BOOT-INCOMPLETE.
- Tool connector unavailable: capability marked BLOCKED for this session.
- Conflicting current source: stop dependent writes until reconciled.

## Exit
Session context loaded, evidence baseline recorded, current task and authorized next action identified.
