# Blind Sniper Native Skills

Skills are task-specific operating procedures. Read the relevant `SKILL.md` before execution. Skills are deliberately runtime-neutral: they guide ChatGPT, Codex, OpenHands or Forge only to the extent that the host exposes the required tools.

## Skill index

| Skill | Trigger | Core result |
|---|---|---|
| `agent-dispatch` | Delegate a bounded task to an external worker | Correlated dispatch, receipt and retrieved result |
| `blind-sniper-continuity` | Session boot, technical state recovery or closeout | Provenance-tagged continuity without private-data leakage |
| `browser-operations` | Website interaction or authenticated browser task | Browser action log and outcome |
| `codex-environment-maintenance` | Add/update profiles, skills, agents, tools or templates | Versioned environment change with validation |
| `git-workflow` | Commit, branch, rebase, conflict, push | Deliberate, reversible version-control change |
| `github-research` | Investigate GitHub repositories, source trees, commits and provenance | Evidence-backed repository research |
| `github-workspace` | Any repository, issue, PR or workflow task | Evidence-backed GitHub operation |
| `memory-and-continuity` | Material decision, authorized memory operation or session close | Provenance-tagged state; private memory remains blocked until private storage is verified |
| `multi-session-pr-coordination` | Open/update/merge a PR with concurrent sessions | Safe PR coordination without clobbered heads |
| `owner-policy` | Always active | Standing Owner rules applied under the active delegation |
| `security-and-permissions` | Auth, secrets, permissions, MCP or sensitive operations | Threat/risk review and approval gates |
| `test-and-evidence` | Verify code, config or runtime behavior | Commit-bound verification ledger |
| `web-research` | Research, comparison, current facts or external docs | Source-grounded research brief |
| `workflow-authoring` | Reusable automation or CI workflow | Triggered, bounded workflow contract |

## Skill authoring contract

Each skill must contain YAML metadata: `name`, `description`, `triggers`, `risk`, `required_tools`; and sections for purpose, prerequisites, permissions, procedure, evidence, failure handling and completion criteria.

Do not mark a skill as automatically installed or loaded unless the active host proves that behavior.

## Finding and adapting skills

Two read-only tools keep the catalog usable as it grows:

- `python scripts/find_skill.py "<what you need to do>"` searches every indexed
  skill (native + OpenHands mirror) by matching your description against each
  skill's id, description and triggers. Use `--profile <id>` to restrict to a
  profile's skills, `--list` to list all, `--json` for machine output, and
  `--validate` to audit the catalog (every entry has a file with a description;
  native skills that shadow a same-named mirror skill are reported as notes).
- `python scripts/adapt_skill.py <source-skill-or-path>` turns an external or
  mirror skill into a native contract scaffold that already conforms to the
  authoring contract above, carrying over the description and triggers and
  recording provenance. It is a dry run by default; `--write` creates
  `chatgpt-home/skills/<id>/SKILL.md` and registers the skill in
  `runtime/skills.index.json`. The generated file is a DRAFT: fill the body,
  set the real risk level, and confirm permissions before relying on it.

Neither tool activates anything. Adapting a skill records a contract; it does
not make the host load it.
