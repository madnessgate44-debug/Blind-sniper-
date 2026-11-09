# Workflow — Release Gate

## Required evidence
- Scope and exact release commit.
- Requirements-to-test matrix.
- CI jobs/steps and test logs.
- Independent review findings.
- Secrets/auth and data migration review.
- Deployed smoke test where applicable.
- Monitoring, rollback and incident owner.
- Active standing Owner delegation covering this exact repository/action, or explicit current-session Owner approval when outside the delegated scope.

## Decision
- GO: all required evidence passes, the action is covered by a valid standing delegation or explicit Owner approval, and rollback is defined.
- NO-GO: any blocker, failing check, missing rollback, unknown cost, or action outside the active authority scope.
- CONDITIONAL: only for explicitly accepted residual risk with a named Owner decision.

A green build is necessary where configured, but never sufficient by itself.
