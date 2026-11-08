---
name: testing-strategy
description: "This skill should be used when the user asks to \"write tests\", \"plan testing\", \"fix a flaky test\", \"improve coverage\", or mentions unit, integration, or e2e tests."
triggers:
- test plan
- coverage
- unit test
- integration test
- e2e
---

# Testing Strategy

- Test real code paths, not mocks. Mock only at true system boundaries, and say why.
- Cover the pyramid: many fast unit tests, fewer integration tests, a thin e2e layer.
- Every bug fix gets a test that fails before and passes after.
- Treat a flaky test as a bug; never retry it into green.
- Assert on observable behaviour and side effects, not on internals.
