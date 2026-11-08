---
name: architecture-and-adr
description: "This skill should be used when the user asks to \"write an ADR\", \"design the system\", \"choose a technology\", \"record a decision\", or mentions architecture, trade-offs, or design docs."
triggers:
- architecture
- adr
- system design
- design doc
- trade-off
---

# Architecture and ADRs

- One decision per ADR: context, options considered, decision, consequences.
- Record rejected options and why, so the choice is not relitigated later.
- Prefer the smallest design that meets the requirements; note how it scales.
- Identify failure modes, data ownership, and boundaries explicitly.
- Mark unknowns; do not present an assumption as a decision.
