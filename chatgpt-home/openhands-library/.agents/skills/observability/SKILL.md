---
name: observability
description: "This skill should be used when the user asks to \"add logging\", \"add metrics\", \"add tracing\", \"set up alerts\", or mentions monitoring, instrumentation, or production diagnosis."
triggers:
- logging
- metrics
- tracing
- monitoring
- alerting
---

# Observability

- Structured logs with correlation IDs; never log secrets or personal data.
- Emit the metrics that map to user-visible outcomes, plus error rates and latency.
- Alert on symptoms users feel, not on every internal blip.
- Make each alert actionable; an alert nobody acts on is noise.
