# Repository Guidance

This repository is the account-level OpenHands **plugin**: skills, sub-agents and lifecycle hooks
that load into every conversation. It is registered as a personal marketplace
(`github:madnessgate44-debug/Openhands`, `repo_path: .agents`, `auto_load: true`).

## Layout

```
.agents/                     # the marketplace root (repo_path)
  .plugin/marketplace.json   # marketplace manifest: declares one plugin
  plugin.json                # Agent Plugins 1.0.0 manifest (the plugin)
  skills/<name>/SKILL.md     # 28 keyword-triggered skills (AgentSkills format)
  skills/<name>.md           # 3 path-triggered rules (frontmatter `paths:`)
  dev.openhands/
    agents/<name>.md         # 19 sub-agents (YAML frontmatter)
    hooks/hooks.json         # lifecycle hooks
    hooks/guard.py           # PreToolUse guard decision logic
    hooks/guard.sh           # PreToolUse guard wrapper -> guard.py
    hooks/quality_gate.sh    # Stop gate
scripts/validate.py          # validates every manifest, frontmatter, skill and hook
tests/hooks_test.sh          # exercises the guard and the quality gate
.github/workflows/validate.yml  # runs both on every PR
```

A marketplace alone loads **only** skills. Agents and hooks load because the marketplace declares a
plugin (`plugins: [{source: "."}]`) and the plugin carries them under `dev.openhands/`. Keep that
indirection: dropping it silently drops the agents and hooks.

## Rules

- One `SKILL.md` per skill folder; a lowercase hyphenated `name` matching the folder.
- Quote any frontmatter scalar YAML would misread (a number like `"502"`, or a colon).
- The sub-agent tool name is `browser_tool_set`, never `browser`. A wrong name registers the agent
  but makes it fail at instantiation.
- Sub-agent `skills:` resolve against the **workspace**, not this plugin, so do not wire plugin
  skills into a sub-agent; that fails whenever the workspace lacks them.
- Validate before committing: `python3 scripts/validate.py` (parses every manifest, frontmatter,
  skill trigger and hook) and `bash tests/hooks_test.sh` (guard allow/deny cases and the quality-gate
  loop breaker). CI runs both on every pull request. A single malformed file silently drops that
  component.
- A skill with neither `triggers:` nor `paths:` loads as legacy always-active: its full text sits in
  `<REPO_CONTEXT>` on every turn. If both `paths:` and `triggers:` are set, `paths:` wins and the
  `triggers:` are ignored with a warning. Prefer one or the other.
- Start a new conversation after changing a component for the catalog to rebuild.
