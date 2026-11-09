---
name: github-research
description: Inspect GitHub repositories, source trees, agents, skills, workflows and licenses; import reusable assets with provenance.
triggers: inspect GitHub project, import skills, compare harness, audit source repo
risk: low
required_tools: GitHub repository fetch and search; branch/file writes only when explicitly authorized
---

# GitHub Research Skill

## Purpose

Produce a reproducible, evidence-backed assessment of GitHub repositories and their reusable operating-system components.

## Prerequisites

- Resolve the exact owner/repository identity and default branch.
- Record the current source commit or tree SHA.
- Read repository instructions and license terms before considering reuse.
- Distinguish source content from inferred capability or runtime behavior.

## Permissions

- Repository and file inspection is read-only by default.
- Create or update destination files only on an authorized feature branch.
- Do not import unlicensed source code without permission or a confirmed applicable license.
- Never activate imported shell scripts, workflows, hooks, MCP servers or credentials merely because they were copied.
- Do not merge, push to a protected/default branch, deploy or alter CI permissions without explicit current-session authorization.

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

## Evidence

Record repository URL, owner, default branch, source commit/tree SHA, file blob SHAs, license evidence, destination paths, changes, validation commands and exact outputs. Clearly distinguish 404/unavailable sources from similar but non-equivalent candidates.

## Failure handling

- Missing or ambiguous repository identity: do not guess or silently substitute.
- Missing license: classify source code as not reusable until permission/license is confirmed; independently authored patterns may be documented with attribution.
- Truncated trees, inaccessible files or API errors: report the exact gap and avoid completeness claims.
- Schema, reference or validation failures: stop adoption until corrected.

## Completion criteria

A repository audit has an exact source identity and revision, evidence-backed inventory, license/provenance decisions and explicit adopt/adapt/reject/blocked outcomes. An import is complete only when the destination manifest and validation evidence match the actual imported files.
