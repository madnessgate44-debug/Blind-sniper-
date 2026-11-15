# BS-MEMORY-001 — Evaluation Matrix

This matrix defines the synthetic evaluation gate for the native memory plane. Fixtures contain no real owner, child, client, or conversation data.

| Area | Required behavior | Automated evidence |
|---|---|---|
| Secret hygiene | Recognized credentials are redacted; sensitive keys/classifications are rejected | `test_blind_sniper_memory.py` |
| Capture provenance | Closed schema, digest, source/event allowlists and timezone validation | `test_blind_sniper_memory.py` |
| Idempotency | Exact replay is a duplicate; conflicting ID reuse is rejected | `test_blind_sniper_memory.py` |
| Public/private boundary | Journal, proposal, approval and handoff paths must be outside the public checkout and owner-only | Memory journal, knowledge and handoff path tests |
| Runtime capture | Native daemon records task-created and task-transition metadata only; capture errors do not stop task execution | `test_blind_sniper_memory_runtime.py` |
| Consolidation | Proposals preserve source IDs, remain proposed, and create immutable superseding versions | `test_blind_sniper_memory_knowledge.py` |
| Conflict handling | Competing statuses remain visible as evidence; no automatic conflict resolution | `test_blind_sniper_memory_knowledge.py` |
| Approval | Only the exact reviewed proposal identity can be promoted to a separate approved copy | `test_blind_sniper_memory_retrieval.py` |
| Retrieval | Only approved pages in the requested project/scope are returned; context is byte-bounded and provenance is retained | `test_blind_sniper_memory_retrieval.py` |
| Handoff packet | Closed packet, atomic claim-once, owner-only storage, tamper checks and task-state re-read | `test_blind_sniper_memory_handoff.py` |
| Model handoff tool | Lease-bound tool receipt, registered recipient, retry idempotency, one outgoing handoff per task/agent, depth bound | `test_blind_sniper_tool_runtime.py` |
| Daemon delivery | Parent must be COMPLETED; claim and recovery precede idempotent child-task creation; child resumes with parent ledger state | `test_blind_sniper_daemon.py` |
| No replay | Repeated daemon polls do not re-invoke completed parent or child tasks | `test_blind_sniper_daemon.py` |
| Recovery knowledge | Non-approved knowledge is rejected | `test_blind_sniper_memory_handoff.py` |

## Explicitly unproven

- A resident private host has not been activated; therefore cross-process/cross-session memory persistence has not been demonstrated on the Owner's actual host.
- Real model-provider execution of `agent.handoff` and persistent-host restart recovery have not been exercised; current evidence uses deterministic injected model invokers.
- No real personal memory or ChatGPT transcript capture is enabled.
- No multi-process stress test or fault-injection test has been run against a live private host.
- Lexical retrieval has not been benchmarked against a representative real workload; SQLite FTS5 and vector search remain deferred.
- Model-assisted summarization and semantic retrieval are not part of this evaluation.

## Latest exact PR-head evidence — 2026-11-14

PR head: `ad51941e7cf6e88a1d14e8a3ada277a61f5329f4`.

- Memory workflow run `43609588105`: 28 memory + 13 native tool-runtime + 21 daemon tests PASS (62 total).
- Runtime Registry run `43609588165`: 285 tests PASS.
- OS Compliance run `43609588150`: PASS.
- Environment Validation run `43609588173`: PASS (49 required assets, 14 skill contracts, 9 agent contracts, 9 workflows, 6 safe Codex config templates).
- Browser Adapter run `43609588114`: 22 adapter + 9 dispatch tests PASS (31 total).

A passing synthetic suite is contract evidence, not proof of live deployment, real provider handoff or operational persistence.

## Durability hardening — 2026-11-15

- [V] Review found that `write_handoff` fsynced packet contents but did not fsync the parent directory entry. A crash could lose the new filename after a successful return.
- [V] `scripts/blind_sniper_memory_handoff.py` now fsyncs the containing directory before returning `CREATED`, and also on the identical-packet retry path.
- [V] Regression test `test_write_handoff_fsyncs_parent_directory_before_success` verifies that a directory descriptor is passed to `fsync`.
- [V] Exact code/test head `233676877817beec895e4b82d9d09f70cb6e72ed`: Memory Tests run `43689998831` PASS; Runtime Registry `43689998742` PASS; OS Compliance `43689998739` PASS; Environment Validation `43689998726` PASS; Browser Adapter `43689998750` PASS.
- [U] Independent third-party review, real provider handoff, owner-controlled private daemon activation, and live-host crash/restart testing remain outstanding.
