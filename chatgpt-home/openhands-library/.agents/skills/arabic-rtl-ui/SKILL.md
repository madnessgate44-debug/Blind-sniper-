---
name: arabic-rtl-ui
description: "This skill should be used when building or changing any Arabic or right-to-left interface, copy or layout, or when the user mentions Arabic, RTL, bidi, Egyptian dialect, or localisation."
triggers:
- arabic
- rtl
- bidi
- egyptian
- localisation
- locale
---

# Arabic and RTL UI

- Set `lang="ar"` and `dir="rtl"` on the root element. Use `dir="auto"` on free-text user input.
- Use logical CSS (`margin-inline-start`, `padding-inline-end`, `inset-inline-*`), never left/right. In Tailwind use `ms-`, `me-`, `ps-`, `pe-` and the `rtl:` variant.
- Mirror directional icons (back, next, progress). Do not mirror media controls, logos or numbers.
- Wrap embedded LTR text (English names, URLs, code) in `<bdi>` or set `dir="ltr"` on it so punctuation does not jump.
- Never bake text into images.
- Use a font stack with real Arabic coverage and a fallback. Load no font from a service that needs a card.
- Format dates and numbers with `Intl` and an Arabic locale; do not hand-build them.
- Follow the project's existing dialect and spelling decisions (for example one fixed spelling of a brand or teacher name). Do not mix Modern Standard and Egyptian Arabic on one screen unless the project already does. Read the project's `AGENTS.md` first.
- Test at 390x844 with long Arabic strings and with mixed English. Check that nothing overlaps or clips.
