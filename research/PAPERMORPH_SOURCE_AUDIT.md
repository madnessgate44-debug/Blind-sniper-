# Papermorph source audit — Miss Noor Educational Media Engine

**Audit baseline:** `DozenTwelve/Papermorph` commit `839a62cad3c74446944a167faff07c994f33e5b7`  
**Audit date:** 2026-11-21  
**Scope:** Read-only source and documentation inspection. No upstream code executed, installed, copied or modified.  
**Disposition:** CONDITIONAL — useful reference and possible selected-component donor; not approved as the product engine.

## 1. Findings

### A1 — Product capability fit

**[VERIFIED]** The upstream lesson workflow is materially relevant: PDF intake and page mapping; extraction; beat/narration authoring; storyboard; SVG/JavaScript animation; formative questions and chapter practice; review/lint; static-site delivery. The lesson kit has a player, timed beats, caption/audio timing, numeric answer checking and interactive question types.

**[VERIFIED]** Other tiers cover picture books, documentary films, vertical shorts, scroll stories and explorable maps. These are useful adjacent capabilities, but the first Miss Noor pilot should remain a bounded lesson, not attempt all tiers.

**[INFERENCE]** The strongest potential reuse is the static player/rendering model, beat timeline, synchronized narration/caption timing, math/diagram helpers and browser QA. The upstream skill orchestration itself is not suitable as Miss Noor's product architecture.

### A2 — Host and orchestration coupling

**[VERIFIED]** Upstream identifies itself as a Claude Code Skill and documents installation for Claude Code/OpenCode. Its workflow expects a host capable of starting models/workers and following skill instructions.

**Decision:** Do not install its host skill as a Blind Sniper runtime dependency. If components are reused, call them through a native, host-neutral Miss Noor media-job contract. Blind Sniper owns durable task state, scheduling, retries, model invocation and artifact receipts.

### A3 — Arabic and language support

**[VERIFIED]**
- `engine/engine.js` contains an Arabic (`ar`) player-interface translation object and sets document direction to RTL for Arabic.
- `references/core/sound.md` documents Edge TTS Saudi voices `ar-SA-HamedNeural` and `ar-SA-ZariyahNeural`, and describes Arabic word-boundary timing including diacritics and Arabic-Indic digits.
- `new_book.py --lang` changes language metadata and audio paths, but its own help explicitly says template text and voice remain English until translated.
- The lesson template therefore is not an Arabic lesson merely because `lang=ar` is set.
- Kokoro is documented as local, but its documented voice/timing support is English. It is not a verified local Arabic TTS path.

**Decision:** Arabic is a real candidate capability, not yet an accepted end-to-end feature. Translation of all lesson copy, player labels, quiz instructions, captions, math directionality, fonts and screen-reader labels must be tested. Edge TTS is online; no privacy/terms/no-card assurance was established in this source audit.

### A4 — Cost and provider boundaries

**[VERIFIED]** The documentation labels Edge TTS and Kokoro free; it identifies `paint.py`, `paint_openai.py`, `eleven.py` and `video.py` as paid/credentialed paths. The code reads OpenRouter/OpenAI credentials for those paths.

**Decision:** Exclude all paid scripts and credentials from the first pilot. Use original code-drawn diagrams and locally available assets; do not call image generation, paid narration, video generation or OpenRouter. Edge TTS may be tested only after its online data handling and service terms are separately reviewed. “MIT licensed” does not mean model inference, TTS, hosting or all content is free.

**[UNPROVEN]** A complete no-card, zero-spend, reliable Arabic voice production route. Kokoro's first local run downloads approximately 330 MB and does not solve Arabic voice support.

### A5 — Security and supply-chain observations

**[VERIFIED]**
- No root `pyproject.toml`, `uv.lock`, `requirements*.txt`, `package.json` or package lock was present in the pinned tree. Dependencies are invoked ad hoc via `uv run --with ...`, with some checks using `pipx run ruff`.
- CI runs skill-link/script checks, TTS text checks, Ruff, sound self-tests and site/JavaScript lint. CI workflow uses major-version action references (`actions/checkout@v5`, `astral-sh/setup-uv@v6`); Ruff is not pinned to an exact version in the workflow.
- `engine.py` can download a GitHub tarball with `urllib.request` when a local engine is absent. The default engine is a moving release tag (`engine-v2.12`), not the reviewed source commit. Any reuse must override this with a verified immutable source and hash.
- `new_book.py` accepts a user-supplied book slug and constructs paths from it; it also removes the generated `site/<book>` directory on failure. A native wrapper must validate slugs and enforce a sandboxed output root before invoking it.
- `serve.py` binds to loopback (`127.0.0.1`) and implements byte-range responses; this is appropriate for local preview, not a public production server.
- Paid scripts contain direct outbound API calls. They must remain unreachable from a zero-cost pilot's allowlisted execution plan.
- PDF parsing uses PyMuPDF. Treat all source PDFs as untrusted input; process in a restricted worker with file-size/page-count/time limits and no credentials.

**[UNPROVEN]** A complete security review of every upstream script, browser behavior, third-party dependency, generated HTML/JS path and every asset/license in all 8,587 tree entries. This document is a scoped initial audit, not a security certification.

### A6 — Licensing and content rights

**[VERIFIED]**
- Root code license is MIT; preserve its copyright and permission notice for any copied substantial code.
- Bundled MathJax includes its own Apache-2.0 license.
- Font files carry separate SIL Open Font License notices; icons carry a separate license notice.
- Published sample books, pictures, audio, maps, third-party images and other assets are not automatically covered by the root MIT license. Audit each asset independently before reuse.
- The Grade 5 French Science PDF located in the user's Library contains a Ministry copyright notice prohibiting reproduction without prior written permission. Its canonical edition identity was not established by the earlier reconstruction record.

**Decision:** Do not copy the textbook PDF, page images, illustrations, wording, exercises or answer layouts into Blind Sniper or a public deployment. Do not use Papermorph's own AGENTS.md-prohibited workflow to create a derivative lesson from a copyrighted textbook. A curriculum-aligned, independently authored lesson may use unprotected scientific facts and learning objectives, with original wording, examples, diagrams and assessments; the legal basis and scope must be checked before public distribution. Do not claim the PDF is openly licensed.

## 2. Reuse decision

| Component | Decision | Reason |
|---|---|---|
| SVG/JS player and timed beat model | Candidate for isolated prototype | Strong fit; inspect dependencies, Arabic rendering and runtime contract first |
| Narration timing/captions | Candidate, conditional | Arabic Edge timings documented; online service and privacy remain unverified |
| Lesson question widgets/grading | Candidate for isolated tests | Useful interaction patterns; verify correctness and accessibility |
| Papermorph Skill / host orchestration | Reject as runtime dependency | Claude Code/OpenCode coupling |
| Paid image/voice/video scripts | Exclude | Violates zero-cost/no-card pilot constraint |
| Published sample book assets | Exclude pending per-asset rights audit | Root MIT license does not cover all content |
| PDF extraction scripts | Candidate only in sandbox | Untrusted input and path/resource limits required |
| Upstream full-repository copy | Reject | Excessive scope, licensing burden and host coupling |

## 3. Verification ledger

| Check | Evidence | Result |
|---|---|---|
| Pin upstream baseline | GitHub branch API: `main` → `839a62cad3c74446944a167faff07c994f33e5b7` | PASS |
| Inspect root license and AGENTS | `LICENSE`, `AGENTS.md` at pinned commit | PASS |
| Inspect lesson workflow and authoring | `references/lessons/lessons.md`, `intake.md`, `authoring.md`, `questions.md`, `checks.md` | PASS |
| Inspect sound/language behavior | `references/core/sound.md`, `scripts/tts.py`, `scripts/new_book.py`, `engine/engine.js` | PASS |
| Inspect workflow and dependency declarations | `.github/workflows/checks.yml`, recursive tree manifest scan | PASS — no root lock/manifest found |
| Inspect outbound/paid paths | `scripts/engine.py`, `tts.py`, `eleven.py`, `paint.py`, `paint_openai.py`, `video.py` | PASS — paths identified, not executed |
| Run upstream CI or scripts | No local checkout/execution environment used | NOT RUN |
| Full code/security audit | Not completed | NOT RUN |
| Mobile Arabic rendering/TTS | No generated pilot artifact | NOT RUN |
| Zero-cost production proof | No provider calls made | NOT RUN |

## 4. R1 disposition

**PARTIAL PASS — source, license and major execution-path inventory completed.** Full dependency and code security review remains open. No upstream code was installed, copied or run. Continue only with a bounded, isolated prototype and the architecture gates in the product specification.
