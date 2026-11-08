# Claude Independent Review Handoff — BS-20261108-004

**Repository:** `madnessgate44-debug/Blind-sniper-`
**Pull request:** [#11](https://github.com/madnessgate44-debug/Blind-sniper-/pull/11)
**Review branch:** `feat/blind-sniper-browser-adapter-2026-11-08`
**Review head at handoff creation:** `9d70385e06d808475e1ca853425d8d1829da4f0b`
**Base branch:** `feat/blind-sniper-orchestration-integration-2026-11-08`
**Mode:** READ-ONLY. Do not push commits, edit files, approve/merge, or alter secrets/settings.

## Review objective

Independently determine whether the browser adapter and persistent-host preparation are safe, correct, complete within the stated scope, and accurately represented by the CI evidence. Do not rely on the author's summary; inspect the full PR diff and source at the exact head above.

## Main changed areas

- `scripts/blind_sniper_browser.py`: browser policy, CLI argument construction, action execution, URL redaction, receipts, file containment and state.
- `scripts/blind_sniper_browser_dispatch.py`: native task/lease gate, pre-action reservation, completion receipt.
- `scripts/blind_sniper_ledger.py`: local/GitHub CAS reservation paths and event ledger.
- `scripts/run_blind_sniper_browser_e2e.py`: two-cycle real Chromium E2E, interruption/reconciliation, tabs/frames, upload/download/PDF.
- `scripts/run_blind_sniper_browser_persistence_probe.py`: two-job self-hosted session persistence probe.
- `tests/test_blind_sniper_browser.py`, `tests/test_blind_sniper_browser_dispatch.py`, `tests/fixtures/browser/**`: unit and fixture coverage.
- `.github/workflows/blind-sniper-browser.yml`: ephemeral CI plus opt-in self-hosted jobs.
- `ops/oracle-free/bootstrap-self-hosted-runner.sh`, `ops/oracle-free/README.md`: Always Free ARM64 bootstrap.
- `chatgpt-home/runtime/{BROWSER_ADAPTER.md,ADAPTER_CONTRACT.md,capabilities.json,workflows.json,README.md}` and task/checkpoint docs: capability and evidence records.

## Required review lenses

1. **Native authority boundary**
   - Verify task status, implementer identity, active lease, lease time budget and reservation are checked immediately before every external browser action.
   - Check that callers cannot self-approve, bypass the dispatcher or forge an owner identity through task content.
   - Examine local lock and GitHub Contents SHA-CAS concurrency, idempotency and replay handling.

2. **Browser action policy**
   - Confirm every CLI command maps to the correct pinned `agent-browser@0.41.2` syntax and correct action-policy permission.
   - Verify tabs and frame changes cannot leave stale origin state or bypass the domain allowlist.
   - Verify the allowlist is not misrepresented as an OS/network firewall.

3. **File and data safety**
   - Audit path traversal, absolute paths, symlink escapes, existing-file overwrite, nested paths, size limits and file-type allowlists.
   - Check upload approval and download/PDF artifact handling.
   - Inspect receipt/session-state URL redaction for secrets in paths, query strings, fragments, command arguments, stdout/stderr and exceptions.

4. **Persistent-host bootstrap**
   - Validate Oracle Always Free quota claims, ARM64 runner install, Node.js and Chrome for Testing ARM64 download, package dependencies, executable path, permissions and systemd EnvironmentFile.
   - Check registration-token exposure and runner scope.
   - Verify no public CDP/debug port or unauthenticated MCP endpoint is exposed.
   - Assess Oracle idle reclamation and region capacity limitations.

5. **Cross-job recovery**
   - Inspect the optional two-job probe's TaskLedger/lease lifetime, session ID, state path, runner affinity and fixture lifetime.
   - Determine whether the test truly proves the same live browser/page survives job cleanup, rather than merely re-opening a browser session from files.
   - Identify any concurrency race from multiple self-hosted runners or simultaneous workflow dispatches.

6. **Evidence and documentation**
   - Verify browser run [42496827462](https://github.com/madnessgate44-debug/Blind-sniper-/actions/runs/42496827462), including the browser-policy suite, dispatcher suite, two Chromium cycles, action counts, receipts and artifact.
   - Confirm latest-head checks separately; do not treat a prior successful code run as evidence for later edits.
   - Identify stale or contradictory status records.
   - Confirm no claims of production hosting, direct ChatGPT tool registration or authenticated profile support are made.

## Known facts and explicit limits

- Browser run 42496827462 passed two consecutive real Chromium cycles. Each cycle recorded 18 started, 17 completed, one started-only interruption reconciled without replay, and 18 receipts. Both cycles exercised tabs, frame switching, upload, download and PDF. Total: 36 receipts; 38,746 screenshot bytes.
- Artifact ID: `13623019051`; SHA-256: `c4615fb9f7b98c9ddf78a9d05b385d72a773b04f1abedd8b082af69ea09825b4`.
- No Oracle tenancy/VM has been provisioned. The ARM64 bootstrap and two-job probe are prepared but not tested on a real Oracle host.
- Oracle Always Free compute may be reclaimed after seven days below published utilization thresholds.
- Direct ChatGPT custom MCP registration is unavailable on the current Free plan; custom MCP connections are web-only. No direct ChatGPT tool registration is established.
- Authenticated browser profiles, cookies and credential-state transfer are intentionally unsupported.
- No Vercel project is linked to this Python runtime repository.
- PR #11 remains DRAFT / OPEN / UNMERGED. Independent review is a release gate.

## Required report format

Use `chatgpt-home/templates/REVIEW_REPORT.md`:

- Verdict: BLOCKED / APPROVE WITH NOTES / APPROVE.
- Findings with severity, exact file/line, evidence, impact, reproduction and required correction.
- Coverage of requirements, security/permissions, error paths, tests, runtime evidence, scope drift and residual risks.
- Explicit owner-only gates for merge, deployment, secrets/permissions and spend.

If no findings exist, state what you inspected and the exact head SHA. Do not approve solely because CI is green.
