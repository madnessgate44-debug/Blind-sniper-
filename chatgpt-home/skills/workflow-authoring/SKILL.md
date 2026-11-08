---
name: workflow-authoring
description: Design and implement bounded CI, scheduled, event-driven and agent workflows with safe triggers and observable outcomes.
triggers: automation, GitHub Actions, schedule, webhook, event receiver, background execution
risk: high
required_tools: GitHub workflow files; workflow run inspection; secrets only through approved host controls
---

# Workflow Authoring Skill

## Purpose
Create workflows that are triggered, bounded, observable, idempotent and cost-aware.

## Prerequisites
Specify trigger, timezone, cadence if scheduled, repository, permissions, runner, input contract, output destination and stopping rules.

## Permissions
Do not enable paid compute, external event receivers, broad tokens or new secrets without explicit Owner approval. Prefer GitHub-hosted free-tier-compatible jobs only after quota/cost is understood.

## Procedure
1. Define trigger and exact task envelope.
2. Set minimum GitHub token permissions per job.
3. Add concurrency/idempotency controls and timeout.
4. Bound retries and prevent self-trigger loops.
5. Redact secrets from logs; never print env values.
6. Persist outputs/artifacts and correlation IDs.
7. Add a dry-run or harmless smoke-test mode.
8. Add failure notification and a stop condition.
9. Inspect the actual workflow run, jobs, steps and artifacts after triggering.
10. Record cost assumptions and approval state.

## Evidence
Workflow path, trigger configuration, permission block, run ID, job/step output, artifact and cost boundary.

## Failure handling
If the runner, event receiver or secret is unavailable, fail closed. Do not label a workflow operational from YAML presence alone.

## Completion criteria
A real trigger produces a correlated run and expected artifact; retries and stop conditions are tested.
