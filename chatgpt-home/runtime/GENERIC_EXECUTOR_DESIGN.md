# Generic allowlisted executor

**Status:** IMPLEMENTED — durable allowlisted executor shipped in `.github/workflows/blind-sniper-executor.yml` with receipt schema `scripts/blind_sniper_receipt.py` and tests `tests/test_blind_sniper_receipt.py` + `tests/test_blind_sniper_executor_workflow.py` (2026-11-09).
**Base:** integration `db4e82ad831fbd231689a359d66a1153fc601407`
**Scope:** one task file, one named branch, read-only repository contents, no secrets.

## Minimal contract

1. Accept a task file containing `task_id`, objective, exact branch name, and an ordered list of command IDs.
2. Resolve command IDs only through a host-owned immutable allowlist; reject raw shell strings, unknown IDs, arguments outside each command schema, and path traversal.
3. Initial allowlist: `unit-tests` → fixed `python -m unittest discover -s tests -p 'test_*.py' -v`; `runtime-validator` → fixed `python scripts/validate_blind_sniper_runtime.py`.
4. Check out only the named existing branch at its recorded HEAD; never push, merge, deploy, or modify repository contents.
5. Read task and source files only; provide no write token, secrets, environment dump, or network credentials to the process.
6. Generalize PR #11's lease reservation into core: atomically reserve a unique `task_id/run_id/step_id` under the active owner lease before each command; reject duplicates and expired leases.
7. Require an active owner lease for claim, execution, verification, review and close; record start/completion receipts against the same task and run.
8. Capture stdout, stderr, command ID, start/end timestamps, and exit code; upload logs plus a machine-readable receipt as a workflow artifact, including on failure.
9. Verification passes only when every requested allowlisted command exits zero and the artifact receipt matches task, branch, commit and run IDs.
10. No browser imports, arbitrary shell, package installation, cache mutation, checkout credentials, secrets, or workflow-dispatch side effects.

## Execution boundary

A future workflow file is a CI/CD edit. It was **authorized** by the Owner in the current session ("complete the remaining implementation gaps in order"), within the standing delegation for this repository (`chatgpt-home/AUTHORITY_DELEGATION.md`, covering `ci_cd_edit` / `workflow_edit`). The executor was implemented in a separate PR with the workflow diff inspected, and the tests `tests/test_blind_sniper_receipt.py` and `tests/test_blind_sniper_executor_workflow.py` assert its security-relevant shape. The first real end-to-end run with plan → claim → execute → verify → independent review → close receipts is performed by the Owner via `workflow_dispatch` (a `workflow_dispatch` workflow cannot run until it is present on the default branch).
