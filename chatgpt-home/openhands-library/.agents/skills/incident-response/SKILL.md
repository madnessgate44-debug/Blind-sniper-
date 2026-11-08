---
name: incident-response
description: "This skill should be used when the user asks to \"handle an incident\", \"triage an outage\", \"write a postmortem\", or mentions severity, on-call, rollback, or production being down."
triggers:
- incident
- outage
- sev
- postmortem
- rollback
- on-call
---

# Incident Response

- Assign a severity and an incident lead; stabilize first, root-cause second.
- Prefer the fastest safe mitigation (rollback, flag off) over a speculative fix.
- Communicate on a fixed cadence with what is known, unknown, and next.
- Keep a timestamped timeline as you go; do not reconstruct it from memory later.
- The postmortem is blameless and produces dated action items with owners.
