---
name: docs-evidence-format
description: "Applies to docs and report Markdown. Grade every factual claim and never invent a run."
paths:
  - 'docs/**/*.md'
  - '**/*REPORT*.md'
---

DOCS RULE: Grade every factual claim and never invent a run.

- Label claims Verified / Observed-not-verified / Hypothesis / Blocked.
- Quote the exact command and output behind any Verified claim.
- If something could not be reached (a host, a secret, an API), mark it Blocked and say why. Do not guess.
