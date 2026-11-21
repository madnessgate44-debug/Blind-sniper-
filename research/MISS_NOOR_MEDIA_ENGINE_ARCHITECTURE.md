# Miss Noor Educational Media Engine — preliminary architecture

**Status:** PROPOSED; not implementation-complete  
**Owner product:** Miss Noor  
**Engineering environment:** Blind Sniper  
**Upstream candidate:** Papermorph, isolated behind an adapter; not a mandatory dependency

## 1. Product contract

The engine accepts curriculum intent and approved source references, then produces a reviewed teaching experience. It is not a PDF converter or generic video generator.

A deliverable lesson must include:
- curriculum objective coverage and a source/claim traceability map;
- a coherent teacher-led explanation with age-appropriate pacing;
- original visual explanation (animation, diagram, simulation or scene);
- narration and synchronized captions;
- purposeful learner interaction and formative checks;
- worked feedback, answer validation and remediation;
- technical and pedagogical QA evidence;
- a versioned, portable learner artifact.

## 2. Logical pipeline

`Curriculum Intake → Learning Design → Script & Storyboard → Media Production → Assembly → Assessment QA → Pedagogical Review → Package & Publish`

### Stage contracts

1. **Curriculum intake**
   - Record grade, curriculum, school track, subject, unit, lesson, instructional language and edition.
   - Accept approved learning objectives, teacher notes and rights/provenance metadata.
   - Preserve uncertainty; never infer an official school assignment from a generic curriculum book.
2. **Learning design**
   - Decompose objectives into prerequisite knowledge, concepts, misconceptions, vocabulary, observable success criteria and assessment evidence.
   - Create a traceability matrix: objective → explanation → visual → interaction → assessment.
3. **Script and storyboard**
   - Author original narration and examples.
   - Define each scene/beat with narration, visual state, timing marks, interaction, caption and transition.
   - Require teacher review before expensive or irreversible production steps.
4. **Media production**
   - Deterministic code-rendered diagrams/animations first.
   - Optional asset providers behind explicit capability/cost policies.
   - Narration provider is replaceable; no provider owns task state.
5. **Assembly**
   - Build a self-contained static lesson package with versioned assets, metadata, player and offline/low-bandwidth behavior where feasible.
6. **Assessment QA**
   - Execute answer-key tests, distractor/rationale checks, question navigation, replay/seek, score persistence and keyboard/touch interactions.
7. **Pedagogical review**
   - Verify scientific accuracy, grade appropriateness, objective coverage, language correctness, misconceptions and accessibility.
   - Reject a lesson that is visually polished but instructionally incomplete.
8. **Package and publish**
   - Emit a versioned lesson package and QA receipt.
   - Hosting is a separate deployment concern; no paid host is assumed.

## 3. Core data contracts

The first implementation should use versioned JSON schemas (strict validation, unknown fields rejected unless schema version allows them). Suggested records:

- `MediaProjectSpec`: project id, grade, curriculum, subject, school track, languages, source provenance, rights policy, learner profile constraints.
- `LessonSpec`: lesson id, title, objectives, prerequisites, vocabulary, misconceptions, duration target, instructional sequence, mastery criteria.
- `SourceEvidence`: source id, page/section locator, extracted factual claim, confidence, rights classification, reviewer status. Keep private/copyrighted source payloads outside the public repo.
- `BeatSpec`: stable beat id, teaching purpose, narration segments, visual state/actions, duration constraints, caption language, pause/replay policy.
- `AssetSpec`: asset id, type, origin, license, attribution, checksum, dimensions, alt text and reuse permissions.
- `InteractionSpec`: interaction type, prompt, learner input schema, validation rule, feedback for correct/incorrect/partial answers.
- `AssessmentItem`: objective link, item type, correct answer, rationale, misconception mapping, difficulty and reviewer status.
- `QAReceipt`: schema version, artifact digest, checks run, results, reviewer approvals, known limitations and build provenance.

## 4. Runtime boundaries

### Blind Sniper owns
- durable task lifecycle, queue/lease, retries, interruption recovery and idempotency;
- model-provider invocation boundary (inference only);
- tool permissions, sandboxing, audit receipts and artifact persistence;
- job orchestration and cost policy enforcement.

### Educational Media Engine owns
- curriculum and lesson schemas;
- instructional design and authoring workflow;
- rendering/animation and narration assembly;
- interaction/assessment runtime;
- lesson package and QA evidence.

### Provider adapter contract
A provider receives only a bounded, redacted task input and returns a typed result. It cannot mutate task state, access arbitrary files, choose a paid fallback, or publish artifacts. Provider selection is policy-driven and records model/version, request digest, estimated/actual cost and output digest.

### Papermorph adapter
Treat as one possible renderer/authoring backend. The Miss Noor engine calls it through a stable adapter and can replace it with a native renderer without changing curriculum or lesson data. Do not depend on Claude Code/OpenCode skill execution.

## 5. Language and localization

- Language is explicit per lesson and per narration segment; do not assume player UI language equals instructional language.
- Arabic requires RTL text layout while preserving mathematical notation and diagram geometry; test mixed Arabic/Latin terms, equations, numerals, captions and focus order.
- French science/math terminology must be reviewed against the required school track. English remains an available product language, not a substitute for the actual teaching language.
- A locale flag is not translation. Every learner-visible string, prompt, answer, hint, caption, narration and accessibility label must be localized and reviewed.

## 6. Cost and rights policy

- Default provider policy is free/local/deterministic only.
- Paid routes are disabled by default and cannot be silently selected as fallbacks.
- Every external call must be declared in a capability manifest and cost ledger.
- Source and asset rights are tracked separately. A code license never grants rights to textbook text, scans, figures, audio or sample media.
- Private student information, private source PDFs and private transcripts stay outside the public repository and public lesson package.

## 7. First vertical slice

**Target:** one short Grade 5 French Science lesson, selected from the previously reconstructed Term 1 source map. Candidate topic: Chapter 1, “Les os et les muscles”; first bounded subtopic: how opposing arm muscles contract/relax to bend and extend the arm.

This candidate is not yet an approved canonical school assignment. The reconstructed PDF is a third-party-assembled copy; Ministry imprint was observed but canonical edition identity and school assignment were not proven. The source carries a reproduction restriction. Do not copy its wording, drawings, pages or exercises. The pilot must use original explanations, original diagrams/animation, original questions and independently authored examples, and it must be reviewed against the learning objectives rather than reproduce the book.

Acceptance:
1. objective and vocabulary map approved;
2. 4–7 minute coherent teacher-led lesson;
3. original arm-muscle animation with scientifically correct opposing muscle action;
4. French narration/captions and French terminology reviewed;
5. interactive learner check with correct/incorrect feedback and tested answer key;
6. responsive phone player, replay/seek and audio controls;
7. artifact, tests and QA receipt reproducibly generated;
8. no paid provider, no secrets, no private/copyrighted source files in public repo.

## 8. Explicit exclusions for the first slice

No complete textbook ingestion; no whole-course production; no character casting or Miss Noor visual redesign; no social feed; no accounts or learner analytics; no paid image/TTS/video services; no public textbook reproduction; no production deployment before QA and rights review.
