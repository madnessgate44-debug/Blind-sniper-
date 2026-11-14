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
| Handoff packet | Closed packet, atomic claim-once, owner-only storage, tamper checks and task-state re-read | `test_blind_sniper_memory_handoff.py` |\n| Model handoff tool | Lease-bound tool receipt, registered recipient, retry idempotency, one outgoing handoff per task/agent, depth bound | `test_blind_sniper_tool_runtime.py` |\n| Daemon delivery | Parent must be COMPLETED; claim and recovery precede idempotent child-task creation; child resumes with parent ledger state | `test_blind_sniper_daemon.py` |\n| No replay | Repeated daemon polls do not re-invoke completed parent or child tasks | `test_blind_sniper_daemon.py` |
| Recovery knowledge | Non-approved knowledge is rejected | `test_blind_sniper_memory_handoff.py` |

## Explicitly unproven

- A resident private host has not been activated; therefore cross-process/cross-session memory persistence has not been demonstrated on the Owner's actual host.
- Real model-provider execution of `agent.handoff` and persistent-host restart recovery have not been exercised; current evidence uses deterministic injected model invokers.
- No real personal memory or ChatGPT transcript capture is enabled.
- No multi-process stress test or fault-injection test has been run against a live private host.
- Lexical retrieval has not been benchmarked against a representative real workload; SQLite FTS5 and vector search remain deferred.
- Model-assisted summarization and semantic retrieval are not part of this evaluation.

## Latest exact-head evidence — 2026-11-14

Code checkpoint: `5e4985ba4083e08e0ec4fab5555eab357a189786`.

- Memory workflow run `43609017044`: memory contracts 28 PASS, native tool runtime 13 PASS, daemon integration 19 PASS (60 focused tests total).
- Runtime Registry run `43609016954`: 283 tests PASS.
- OS Compliance run `43609017199`: PASS.
- The subsequent fan-out guard and its regression test were committed after this checkpoint and require fresh exact-head checks.

A passing synthetic suite is contract evidence, not proof of live deployment, real provider handoff or operational persistence.
