# Blind Sniper Native Skills

Skills are task-specific operating procedures. Read the relevant `SKILL.md` before execution. Skills are deliberately runtime-neutral: they guide ChatGPT, Codex, OpenHands or Forge only to the extent that the host exposes the required tools.

## Skill index

| Skill | Trigger | Core result |
|---|---|---|
| `github-workspace` | Any repository, issue, PR or workflow task | Evidence-backed GitHub operation |
| `web-research` | Research, comparison, current facts or external docs | Source-grounded research brief |
| `browser-operations` | Website interaction or authenticated browser task | Browser action log and outcome |
| `agent-dispatch` | Delegate to OpenHands, Forge or another worker | Correlated dispatch/receipt/result |
| `workflow-authoring` | Reusable automation or CI workflow | Triggered, bounded workflow contract |
| `test-and-evidence` | Verify code, config or runtime behavior | Commit-bound verification ledger |
| `security-and-permissions` | Auth, secrets, permissions, MCP or sensitive operations | Threat/risk review and approval gates |
| `memory-and-continuity` | Session boot, material decision or closeout | Provenance-tagged persistent state |
| `codex-environment-maintenance` | Add/update profiles, skills, agents, tools or templates | Versioned environment change with validation |

## Skill authoring contract

Each skill must contain YAML metadata: `name`, `description`, `triggers`, `risk`, `required_tools`; and sections for purpose, prerequisites, permissions, procedure, evidence, failure handling and completion criteria.

Do not mark a skill as automatically installed or loaded unless the active host proves that behavior.
