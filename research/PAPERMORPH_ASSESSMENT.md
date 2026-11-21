# Papermorph — technical assessment and bounded pilot

**Status:** STARTED — research/specification only until implementation gates pass  
**Owner repository:** `madnessgate44-debug/Blind-sniper-`  
**Upstream under read-only review:** https://github.com/DozenTwelve/Papermorph  
**Upstream revision reviewed:** `DozenTwelve/Papermorph` `main` at `839a62cad3c74446944a167faff07c994f33e5b7` (observed 2026-11-21); use this immutable SHA for the audit baseline and re-pin before any later update.  
**Hard constraints:** no payment, no card, no paid compute, no paid external service; no secrets, private memory, child data, textbook PDFs, transcripts, or private project artifacts in this public repository.

## Outcome

Determine whether Papermorph can safely supply a reusable document-to-learning-media capability for Miss Noor, and whether any of its engine or production concepts can be integrated into Blind Sniper without importing its host-specific agent assumptions. Deliver a reproducible, phone-accessible pilot artifact only after the assessment gates pass.

## Verified upstream facts from inspected source

- Papermorph describes itself as an agent skill that creates animated interactive lessons from textbook PDFs, picture-book films, documentaries, shorts, and explorable pages.
- The delivered book is a static folder of HTML, JavaScript, CSS and audio; its documentation says no application server, database or reader account is required. Reading progress is stored in browser localStorage.
- Lesson workflow: PDF intake/splitting, chapter extraction, beat/narration authoring, storyboard, animation/questions, checks/review, static-site delivery.
- The shared player documents English, Russian, Chinese, Japanese and Arabic interface strings; Arabic is right-to-left.
- The narration reference explicitly documents Edge TTS Saudi Arabic voices `ar-SA-HamedNeural` and `ar-SA-ZariyahNeural`, with Arabic word-boundary timing support, including diacritics and Arabic-Indic digits.
- Edge TTS is documented as free but online. Kokoro is documented as local and Apache-2.0 but its documented word timings/voices cover English; it is not an Arabic zero-network substitute.
- Paid optional paths include image generation/painting, ElevenLabs narration and some video generation. The core pilot must not invoke them.
- Upstream says the code is MIT licensed, with bundled MathJax under Apache-2.0; assets/content under `site/` carry their own licenses and must be audited separately.
- Upstream's documented host integrations are Claude Code and OpenCode. Blind Sniper must not assume either host, or rely on their subagent interfaces.

## Requirements and acceptance criteria

### R1 — Source, licence and supply-chain audit
- Pin upstream commit SHA, inspect AGENTS.md, skill entrypoint, all scripts actually needed by a lesson, templates, engine, package/dependency manifests and workflows.
- Produce a component inventory: reusable / adapt / exclude, with paths and license attribution.
- Inspect dependencies and install/build commands for unsafe install hooks, downloads, subprocess execution, network calls, secret handling, filesystem scope and generated-content boundaries.
- Acceptance: every copied or adapted component has a recorded path, upstream SHA, license, rationale and security note. No blind wholesale copy.

### R2 — Blind Sniper compatibility
- Map Papermorph's host assumptions (Claude Code/OpenCode skill invocation, model/subagent launch, user prompts, task coordination) against Blind Sniper's native provider interface, durable task lifecycle, executor, worker and browser.
- Define a host-neutral adapter contract. Model providers supply inference only; they do not own task state or orchestration.
- Acceptance: architecture note identifies the minimum integration seam and proves the plan does not require Claude Code, OpenCode, OpenHands, Forge, or paid services.

### R3 — Free/no-card cost proof
- Separate zero-cost paths from optional paid paths.
- Pilot only with free Edge TTS and deterministic/local rendering; no OpenRouter, OpenAI image generation, ElevenLabs, paid model tiers, subscriptions or card-gated resources.
- Check current provider terms/limits and whether account signup requires a card; if unknown, label UNVERIFIED and do not activate.
- Record actual model/provider calls and cost evidence; never infer free status from an MIT license.
- Acceptance: reproducible cost ledger with actual zero-spend proof for the pilot, or a precise blocker.

### R4 — Arabic and curriculum fidelity
- Confirm Arabic narration generation, word timings, punctuation/captions, RTL layout, math directionality and Arabic fonts in a real browser.
- Distinguish Arabic player translation from Arabic lesson content: translate all lesson template strings, prompts, quiz labels and navigation, not merely set `lang=ar`.
- Test Egyptian Arabic curriculum terminology and Modern Standard Arabic narration separately; record which is used and why.
- Use only an owner-approved or openly licensed source chapter. Do not commit a copyrighted textbook PDF, extracted pages, private curriculum material or child-identifying information.
- Acceptance: one reviewed Arabic sample with a terminology glossary and evidence for audio timing, captions, RTL and mobile readability.

### R5 — Grade 5 science pilot
- Choose one bounded chapter with the Owner; use an approved source and record its provenance/license.
- Preserve the source's learning objectives, concept order, expected difficulty, vocabulary, diagrams and assessment intent. Do not invent missing curriculum facts.
- Produce one short interactive chapter with narration, diagrams/animation, quick checks and chapter practice; make every answer key independently checkable.
- Acceptance: chapter-to-source traceability matrix; educational review; no factual errors; no missing required concepts; all interactive controls work.

### R6 — Phone and browser acceptance
- Test on a real Android/Samsung viewport or a documented equivalent Chromium mobile emulation, then obtain owner confirmation on the actual phone.
- Check portrait and landscape behavior, tap targets, audio start/resume, seeking, captions, RTL, math rendering, weak-network behavior, accessibility and progress persistence.
- Acceptance: screenshots/receipts, browser console/network evidence, test matrix and explicit known limitations. A desktop build alone is insufficient.

### R7 — Delivery and hosting
- Verify static output can be hosted under a subpath on GitHub Pages or the existing approved Vercel/GitHub path without requiring a paid feature.
- Verify relative asset paths, audio MIME/range behavior, cache policy and navigation.
- Keep private source material and production notes outside the public delivered folder/repository.
- Acceptance: reproducible static artifact, deployment evidence if deployment is authorized and available, and a public demo containing only properly licensed/generated material.

### R8 — Integration decision
- Compare (A) use upstream as a separate production tool, (B) vendor selected engine/player components, (C) implement a native Blind Sniper adapter, or (D) reject.
- Evaluate maintenance burden, license obligations, update strategy, security, Arabic gaps, provider cost and mobile quality.
- Acceptance: evidence-backed GO / CONDITIONAL GO / NO-GO recommendation. Do not merge an integration before the pilot passes.

## Execution sequence

1. Pin and inspect upstream revision; complete R1.
2. Complete host-neutral architecture map; complete R2.
3. Validate free/no-card assumptions without entering credentials or triggering paid paths; complete R3.
4. Select one approved Grade 5 science chapter and produce a source traceability map; complete R4/R5.
5. Generate the pilot using only approved free paths; record all commands, exit codes, raw outputs and timestamps.
6. Run automated browser checks and mobile acceptance; complete R6.
7. Verify static hosting path and artifact; complete R7.
8. Publish decision record and only then propose the smallest integration PR; complete R8.

## Explicit non-goals / prohibitions

- Do not modify the Miss Noor/Amina repository under this task. Produce a separate integration proposal for that repository; cross-repository changes require separate authorization.
- Do not copy the whole upstream repository into Blind Sniper.
- Do not import upstream books, copyrighted textbook pages, sample assets, voices, music or data unless each asset's own license permits it.
- Do not activate production workers, recurring jobs, external provider secrets, paid services or paid model routes.
- Do not expose or store any child identity, private memory, family details, private curriculum PDFs or transcripts.
- Do not claim Arabic generation, mobile success, zero-cost production, deployment or integration until directly verified.

## Evidence ledger template

For each check record: exact command/action; exit code or host result; raw output excerpt; timestamp; PASS/FAIL/NOT RUN; artifact path or URL; requirement ID.

## Initial disposition

**CONDITIONAL GO for read-only assessment and one bounded pilot. NO-GO for production integration until R1–R7 have evidence and R8 recommends GO.**