---
name: github-research
description: Inspect GitHub repositories, source trees, agents, skills, workflows and licenses; import reusable assets with provenance.
triggers: inspect GitHub project, import skills, compare harness, audit source repo
risk: low
required_tools: GitHub fetch/search and repository write only when import authorized
---

# GitHub Research Skill

## Procedure
1. Resolve repository, default branch and current commit.
2. Inspect recursive tree, README, license, manifests, skill/agent/workflow directories.
3. Classify each asset as reusable text, host-specific config, executable code, CI workflow or secret-dependent integration.
4. Read exact source files before importing.
5. Preserve upstream paths, license texts and attribution.
6. Never copy verbatim from a repository with no declared license without permission or confirmed applicable license.
7. Never activate imported scripts, workflows, hooks, MCP servers or credentials on import.
8. Record source URL/revision/license/destination/adaptation/test state.
9. Validate schema, references, links and required attribution.
10. Report imported, adapted and excluded assets separately.

## Completion
A source-backed import manifest exists; no unlicensed files or unreviewed executable actions have been activated.
