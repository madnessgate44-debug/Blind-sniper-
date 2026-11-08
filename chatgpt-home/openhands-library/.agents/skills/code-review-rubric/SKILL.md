---
name: code-review-rubric
description: "This skill should be used when the user asks to \"review this PR\", \"review my diff\", \"check this change for bugs\", or mentions code review, pull request feedback, or correctness and security review."
triggers:
- code review
- review
- pull request
- diff
- feedback
---

# Code Review Rubric

- Correctness first: logic, edge cases, error handling, concurrency.
- Security: injection, authz, secrets in code, unsafe deserialization.
- Compatibility: does this break callers, data, or the public contract?
- Maintainability: naming, dead code, missing tests, needless complexity.
- Be specific and actionable; suggest a fix per issue. Separate must-fix from nits.
