---
name: codex-environment-maintenance
description: Evolve Blind Sniper's profiles, skills, agents, tools, workflows, templates and runtime adapters.
triggers: improve Blind Sniper, add a skill, add agent, update profile, Codex environment, settings
risk: medium; high for permission or runtime activation changes
required_tools: GitHub repository operations; validation workflow
---

# Codex Environment Maintenance Skill

## Purpose
Maintain the environment as a versioned product, not a loose collection of prompts.

## Prerequisites
Read the environment manifest, profile blueprint, skill catalog, tool registry, relevant agent contracts and current branch state.

## Permissions
Documentation and scoped configuration assets may be changed on a task branch. Activating tools, changing security defaults, installing connectors, provisioning compute or altering credentials requires explicit approval.

## Procedure
1. Identify capability gap and target layer.
2. Inspect existing assets and source precedents; avoid duplicates.
3. Define behavior, schema, permissions and acceptance tests.
4. Add or update skill/agent/tool/workflow/template assets.
5. Update indexes and capability status.
6. Add automated structural validation where feasible.
7. Run CI and inspect exact job/step evidence.
8. Mark capabilities IMPLEMENTED, HOST-AVAILABLE, INTEGRATION-BLOCKED or NOT-IMPLEMENTED.
9. Record migration/compatibility notes and rollback path.

## Evidence
Changed paths, source references, schema/version, CI run, test results and updated readiness matrix.

## Failure handling
Do not mark a capability live because its configuration file exists. Separate specification, implementation, host installation and successful runtime use.

## Completion criteria
The new capability is indexed, validated, permission-scoped and accurately represented in the runtime status.
