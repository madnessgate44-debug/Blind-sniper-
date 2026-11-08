---
name: performance-engineering
description: "This skill should be used when the user asks to \"make it faster\", \"reduce the bundle\", \"profile this\", \"fix Core Web Vitals\", or mentions latency, memory, or performance regressions."
triggers:
- performance
- profiling
- core web vitals
- bundle size
- latency
---

# Performance Engineering

- Measure before optimizing; capture a baseline and a profile.
- Optimize the actual bottleneck, not the one that looks suspicious.
- For the web: watch LCP, INP, CLS, and bundle size; lazy-load and split.
- For the backend: watch query plans, N+1 access, and payload size.
- Re-measure after the change and report both numbers.
