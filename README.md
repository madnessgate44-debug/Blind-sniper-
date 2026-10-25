# Miss Noor — AI School Companion (live preview)

Live preview build of the Miss Noor app.

**Live site:** https://madnessgate44-debug.github.io/Blind-sniper-/

Miss Noor is an AI school companion for a Grade 5 learner (École Girard,
Alexandria — French track, Egyptian curriculum). Navigation: HOME | FEED |
LIBRARY | NOUR.

## What this repository is

This repository previously hosted an unrelated project. It has been repurposed
as the free hosting playground for the Miss Noor app. The previous contents are
preserved in the git tag `archive/pre-miss-noor-2026-10-25` and remain
recoverable.

## How this build is produced

From the `madnessgate44-debug/Amina` repository:

```bash
npx vite build --base=/Blind-sniper-/
# then copy dist/* to the root of this repository
```

## Limits of this static preview

GitHub Pages serves static files only. The AI routes defined in Amina's
`server.ts` (`/api/chat`, `/api/tutor-*`, `/api/stt`, `/api/tts`,
`/api/check-homework`, `/api/reconstruct-day`) are not present here, so tutor
chat and speech fall back to the app's built-in offline copy. Everything else is
fully browsable: onboarding, HOME, FEED, LIBRARY, NOUR, save/revisit, My Books.

Live model answers require the server target.
