# Blind Sniper Home

This directory is Blind Sniper's durable, version-controlled continuity home in `madnessgate44-debug/Blind-sniper-`.

## Mandatory session-start retrieval
Blind Sniper must fetch and read the complete current contents of all seven files listed below from the repository's default branch before relying on prior continuity. Verify each fetch succeeded and record the fetched blob SHAs and retrieval timestamp in the session checkpoint. Do not rely on stale local copies.

## Read order at the start of a returning session
1. Root `AGENTS.md` and `ENGINEERING_EXECUTION_OS.md` — mandatory controlling execution rules.
2. `chatgpt-home/OPERATING_PROFILE.md` — role, working contract, and communication rules.
3. `chatgpt-home/MEMORY.md` — durable owner and project context.
4. `chatgpt-home/PROJECTS.md` — current project map and priorities.
5. `chatgpt-home/CONVERSATION_CONTINUITY.md` — recovered decision history and open threads.
6. `chatgpt-home/SKILLS_CATALOG.md` — skills and agent-library sources.
7. `chatgpt-home/SYNC_PROTOCOL.md` — how to keep this home current.

## Authority and provenance
- The root Engineering Execution OS v2.2 is controlling; this directory supplements it and does not weaken it.
- This home is a durable summary and index, **not a verbatim export of every ChatGPT conversation**.
- Every fact must retain its evidence status. Mark recovered conversation summaries [RECONSTRUCTED] unless the original message or artifact was directly retrieved.
- GitHub repository state is authoritative for code, PRs, issues, commits, and recorded agent work. This home is authoritative only for ChatGPT's continuity notes.
- Never store API keys, tokens, passwords, private credentials, or secret values here.
- Update these files through reviewed commits. Do not silently overwrite history.
