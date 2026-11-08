---
name: content-vs-brand
description: "Applies to TypeScript source. Treat \"Amina\" in source as content, not branding, unless it is a true brand surface."
paths:
  - 'src/**/*.ts'
  - 'src/**/*.tsx'
---

SOURCE RULE: Treat `Amina` in `src/` as content, not branding, unless it is a true brand surface.

- Most `Amina` strings are the student-name fallback or French/Arabic curriculum text. Changing them breaks content.
- Brand = Miss Noor; the teacher persona is also spelled Miss Noor. Use one spelling in user-visible text.
- UI language is stored in IndexedDB `settings` (`app_settings`), not the student profile.
