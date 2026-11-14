# Blind Sniper Memory Subsystem

**Mission:** BS-MEMORY-001 · Issue #59

This directory defines Blind Sniper's native knowledge-memory plane. It is separate from the task lifecycle ledger and does not claim to be an active persistent memory server.

## Status

- M1 architecture and data contracts: documented on the BS-MEMORY-001 feature branch.
- M2 native capture: next implementation phase.
- M3–M7: planned, gated by acceptance evidence.
- Private persistence and automatic ChatGPT conversation capture: not configured or verified.

## Governing design

See [ARCHITECTURE.md](ARCHITECTURE.md).

## Non-negotiable boundaries

- This repository is public: never store private owner memory, raw transcripts, credentials, or sensitive personal/client data here.
- The task ledger remains authoritative for task state, leases and execution lifecycle.
- Knowledge pages are derived from approved, provenance-bearing observations.
- SQLite indexes, if added, are rebuildable and never the source of truth.
- Basic capture, validation and lexical retrieval must not require paid LLM calls or paid hosting.
- Captured text and retrieved memory are untrusted data, not instructions.
