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
| Handoff | Closed packet, atomic claim-once, owner-only storage, tamper checks and task-state re-read | `test_blind_sniper_memory_handoff.py` |
| Recovery knowledge | Non-approved knowledge is rejected | `test_blind_sniper_memory_handoff.py` |

## Explicitly unproven

- A resident private host has not been activated; therefore cross-process/cross-session memory persistence has not been demonstrated on the Owner's actual host.
- The daemon does not yet automatically create/consume agent handoffs.
- No real personal memory or ChatGPT transcript capture is enabled.
- No multi-process stress test or fault-injection test has been run against a live private host.
- Lexical retrieval has not been benchmarked against a representative real workload; SQLite FTS5 and vector search remain deferred.
- Model-assisted summarization and semantic retrieval are not part of this evaluation.

## Latest exact-head evidence — 2026-11-14

- PR head: `ed16dc40d731ec01550fb5c6ffe3d2d5cbef5935`.
- Memory Tests run `43607326400`: 28 tests, 0 failures.
- Runtime Registry run `43607326369`: 280 tests, 0 failures.
- OS Compliance run `43607326385`: PASS.

A passing synthetic suite is contract evidence, not proof of live deployment or operational persistence.
