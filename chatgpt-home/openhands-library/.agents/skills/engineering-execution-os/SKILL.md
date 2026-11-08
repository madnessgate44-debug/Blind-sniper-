---
name: engineering-execution-os
description: "This skill should be used when the user asks to follow the execution OS, or mentions the verification ledger, the compliance header, or evidence tags."
triggers:
- execution os
- verification ledger
- compliance header
- evidence tag
---

# Engineering Execution OS

Apply the lifecycle below to any engineering task that produces or changes an artifact.

If the repository has an `ENGINEERING_EXECUTION_OS.md`, that file is the controlling procedure:
read it first and follow it. If it is absent, use this embedded minimal version instead and
continue -- do not stop, and do not report BLOCKED just because the file is missing.

## Lifecycle

OUTCOME -> INSPECT -> SPECIFY -> PLAN -> EXECUTE -> VERIFY -> REVIEW -> CLOSE.

- **OUTCOME**: state the observable result the task must produce.
- **INSPECT**: read the real code, config and history before proposing anything.
- **SPECIFY**: turn the outcome into concrete, testable acceptance criteria.
- **PLAN**: list the ordered steps and the evidence each will produce.
- **EXECUTE**: make the smallest change that satisfies the spec.
- **VERIFY**: run the checks for real and record them in the ledger.
- **REVIEW**: re-read the diff for correctness, security and scope creep.
- **CLOSE**: summarize what changed, what was verified, and what remains.

## Evidence tags

Tag every non-trivial claim inline:
[V] Verified, [C] Reported claim, [I] Inference, [A] Assumption, [U] Unknown, [B] Blocker.

## Verification ledger

A check is NOT verified without a ledger entry: the verbatim command, its exit code, a raw output
excerpt, the timestamp, and a PASS/FAIL/NOT RUN verdict.

Never claim a check passed if it was not run. Never fabricate a path, test, result, sync or
deployment. Two consecutive turns with no new evidence or artifact => stop and report BLOCKED.
