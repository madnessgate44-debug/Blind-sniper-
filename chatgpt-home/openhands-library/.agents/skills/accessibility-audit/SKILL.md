---
name: accessibility-audit
description: "This skill should be used when the user asks to \"audit accessibility\", \"check keyboard reachability\", \"fix contrast\", \"add ARIA labels\", or mentions WCAG, a11y, screen readers, or focus states."
triggers:
- accessibility
- a11y
- wcag
- contrast
- keyboard
- screen reader
---

# Accessibility Audit

- Everything reachable and operable by keyboard, with a visible focus state.
- Every control has an accessible name; every image a meaningful alt.
- Contrast meets WCAG AA; never signal meaning by colour alone.
- Test at real viewports, including small phone sizes.
- Verify with the same hit-testing discipline as any UI test; a raw pixel click plus a side effect.
