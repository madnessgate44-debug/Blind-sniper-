# Workflow — Release Gate

## Required evidence
- Scope and exact release commit.
- Requirements-to-test matrix.
- CI jobs/steps and test logs.
- Independent review findings.
- Secrets/auth and data migration review.
- Deployed smoke test where applicable.
- Monitoring, rollback and incident owner.
- Explicit Owner approval.

## Decision
- GO: all required evidence passes and Owner approval is recorded.
- NO-GO: any blocker, failing check, missing rollback, unknown cost or missing approval.
- CONDITIONAL: only for explicitly accepted residual risk with a named Owner decision.

A green build is necessary where configured, but never sufficient by itself.
