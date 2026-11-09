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
