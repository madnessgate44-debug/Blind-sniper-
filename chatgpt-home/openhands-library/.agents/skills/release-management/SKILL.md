---
name: release-management
description: "This skill should be used when the user asks to \"prepare a release\", \"write the changelog\", \"roll out a version\", \"roll back\", or mentions semver, versioning, or deployment."
triggers:
- release
- changelog
- rollout
- rollback
- semver
---

# Release Management

- Version by semver; call out breaking changes explicitly.
- Generate the changelog from merged PRs since the last tag.
- Define the rollout (staged vs all-at-once) and the exact rollback step before shipping.
- Verify the artifact that will actually ship, not a locally built lookalike.
- Record the deployed commit SHA and how to confirm it is live.
