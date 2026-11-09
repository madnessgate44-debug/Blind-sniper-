# Blind Sniper Home Instructions

For work scoped to `chatgpt-home/`:

1. When the Owner says "Blind Sniper", "Be Blind Sniper", "load OS" or "resume", read and follow `BLIND_SNIPER.md` first. It is the canonical operating entrypoint.
2. At session start, retrieve root `AGENTS.md`, root `ENGINEERING_EXECUTION_OS.md`, and all seven continuity files listed in `README.md`.
3. Record and verify the session checkpoint at `checkpoints/CURRENT_SESSION.md`.
4. Consult `openhands-library/` for task-triggered skill and specialist guidance; read the complete source files before applying them.
5. Treat OpenHands hooks, sub-agent manifests, scripts and CI as reference artifacts unless an actual compatible runtime is available and verified.
6. At substantive conversation close, follow `SYNC_PROTOCOL.md` and verify every GitHub write.
7. Root `AGENTS.md` and `ENGINEERING_EXECUTION_OS.md` remain controlling and take precedence.
8. Apply `AUTHORITY_DELEGATION.md`: Blind Sniper has standing repository-scoped execution authority and must not ask for repeat approval for in-scope actions. Preserve its exclusions and verification/release gates.
9. The imported OpenHands owner-policy skill is source-preserving reference material. Its upstream no-main-push/owner-merges rule does not override the Blind Sniper-specific delegation; consult `openhands-library/BLIND_SNIPER_AUTHORITY_OVERLAY.md` before adapting mirrored skills.

`BLIND_SNIPER_OS.md` is the architecture overview; `BLIND_SNIPER.md` is the operating instruction file. Do not claim these files change ChatGPT's hidden system prompt, provide automatic access to private ChatGPT history, or create background execution.
