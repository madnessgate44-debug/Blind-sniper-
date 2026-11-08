---
name: test-and-evidence
description: Build verification plans and validate changes against exact commits using test, CI, smoke and artifact evidence.
triggers: test, verify, end-to-end, audit, acceptance criteria, CI failure
risk: medium
required_tools: relevant test runner or CI; GitHub commit and workflow inspection
---

# Test and Evidence Skill

## Purpose
Turn acceptance criteria into reproducible proof.

## Prerequisites
Identify exact commit/tree, environment, test commands, expected behavior and known baseline.

## Permissions
Tests should be non-destructive. Production probes, load tests, data mutation and external side effects require explicit approval.

## Procedure
1. Map each requirement to a verification method.
2. Separate static checks, unit/integration tests, browser E2E and deployed smoke tests.
3. Run or trigger checks against the exact commit.
4. Capture exact command, environment, exit code, output excerpt and timestamp.
5. Inspect CI job and step details; do not rely only on a green badge.
6. Bind evidence to commit SHA and environment.
7. Run a live smoke test when acceptance concerns deployed behavior.
8. Record failed, skipped and not-run checks explicitly.
9. Re-test after fixes and ensure no regression in previously passing checks.

## Evidence
Use a verification ledger with command/action, environment, commit SHA, exit code, raw output excerpt, timestamp and PASS/FAIL/NOT RUN.

## Failure handling
A reported test count is [REPORTED] until logs or run output are retrieved. Missing test infrastructure is [BLOCKED], not PASS.

## Completion criteria
Every acceptance criterion has a matching evidence record; gaps and limitations are explicit.
