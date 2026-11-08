---
name: security-and-permissions
description: Review tool access, MCP servers, secrets, sandboxing, approval boundaries and threat exposure.
triggers: security, permissions, token, API key, MCP, auth, sandbox, secret, production
risk: high
required_tools: configuration and repository read access; security scanner when available
---

# Security and Permissions Skill

## Purpose
Apply least privilege and prevent accidental credential exposure or authority escalation.

## Prerequisites
Map assets, actors, trust boundaries, data classes, tool permissions and intended operations.

## Permissions
Read-only inspection by default. Never request or place raw credentials in chat or repository files. Secret creation, rotation, disclosure, permission expansion and production changes require explicit Owner approval and an approved secret manager.

## Procedure
1. Identify assets, trust boundaries and threat actors.
2. Inventory credentials by reference/name only; never retrieve secret values.
3. Review sandbox and approval defaults.
4. Restrict MCP tools by allowlist; disable unused tools.
5. Scope GitHub tokens to minimum repositories and permissions.
6. Review browser session and data exfiltration risks.
7. Define audit logging, redaction and incident response.
8. Add negative tests for unauthorized access and missing authentication.
9. Record accepted risks and Owner decisions.

## Evidence
Configuration paths, permission scopes, auth test outcomes, redaction test output and approval record.

## Failure handling
If access scope cannot be inspected or secret state is unknown, mark UNKNOWN and do not activate the integration.

## Completion criteria
Least-privilege policy is documented and tested; all consequential gates are explicit.
