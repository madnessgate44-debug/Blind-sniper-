---
name: data-privacy-compliance
description: "This skill should be used when the user asks to \"handle personal data\", \"add analytics\", \"collect consent\", \"set a retention policy\", or mentions privacy, PII, COPPA, GDPR, or children's data."
triggers:
- privacy
- pii
- gdpr
- coppa
- consent
- children data
---

# Data Privacy and Compliance

- If the project's `AGENTS.md` says it serves children, apply COPPA-style data minimisation; otherwise apply default minimisation.
- Collect the least data that satisfies the need; state retention and deletion.
- Never put personal data in logs, analytics payloads, or the transcript.
- Make consent explicit and revocable.
- Prefer on-device or aggregated data where possible.
