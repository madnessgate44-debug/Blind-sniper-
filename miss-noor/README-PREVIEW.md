# Miss Noor — live preview

Live preview of the Miss Noor app, published here so the owner can see the
current state in a browser without touching the real app.

- Built from `madnessgate44-debug/Amina` @ `0916382` (static build).
- Static only: the `server.ts` AI routes are absent, so tutor chat and speech use
  their built-in offline copy. Everything else works — onboarding, HOME, FEED,
  LIBRARY, NOUR, save/revisit, My Books.
- The Blind Sniper app is untouched; this lives in its own subfolder.
- Rebuild: `npx vite build --base=/Blind-sniper-/miss-noor/` in the Amina repo,
  then copy `dist/` here.
