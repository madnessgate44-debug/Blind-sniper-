---
name: security-threat-model
description: "This skill should be used when the user asks to \"threat-model this\", \"review for security\", \"check for vulnerabilities\", or when a change handles user input, auth, money, or personal data."
triggers:
- threat model
- stride
- owasp
- security review
- auth
---

# Security Threat Model

- Enumerate assets, actors, and trust boundaries; apply STRIDE to each boundary.
- Check the OWASP top risks against the change: injection, broken authz, misconfiguration.
- Secrets never live in code, logs, or the transcript.
- Least privilege for tokens, scopes, and service accounts.
- Record accepted risks explicitly rather than leaving them implicit.
