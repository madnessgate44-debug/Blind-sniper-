# Workflow: Verification → Handoff

**Adapted from:** SUNRNEHUI portable contract, state-witness, TDD gates and 0xenzyme completion evidence.

1. Map each acceptance criterion to an executable check or explicit human review.
2. For state/UI/async/concurrency changes, identify the production state witness and failing/preserved rows.
3. Run the smallest falsifying test first; then required regression and full checks.
4. Capture actual commands, exit codes and concise results. A worker's PASS is only a claim.
5. Inspect the diff and verify no out-of-scope changes.
6. Update durable task state with result, evidence, blockers and next owner.
7. Handoff with exact branch/commit, artifacts, test results, unverified paths and Owner decisions.
