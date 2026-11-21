# Pilot lesson blueprint — Comment les muscles font-ils bouger le bras ?

**Product:** Miss Noor Educational Media Engine  
**Track:** Grade 5 · French Science · Term 1  
**Candidate curriculum unit:** Chapter 1 — *Les os et les muscles*  
**Bounded lesson:** *Comment les muscles font-ils bouger le bras ?*  
**Status:** ORIGINAL CONTENT BLUEPRINT — not yet rendered, narrated, or QA-approved  
**Rights posture:** Original narration, examples, diagrams and questions only. No textbook page, illustration, exercise wording or answer layout is reproduced. The private source PDF is not copied into this repository or build artifact.

## 1. Learning objective

By the end of this lesson, the learner can explain, using the example of the elbow:

1. muscles move bones by pulling on them;
2. during arm flexion, the biceps contracts while the triceps relaxes;
3. during arm extension, the triceps contracts while the biceps relaxes;
4. the elbow is an articulation that allows the bones to move relative to one another.

## 2. Vocabulary

| French term | Learner-friendly meaning |
|---|---|
| un os | a hard part that supports the body |
| un muscle | a soft body part that can contract and pull |
| une articulation | the place where bones meet and movement occurs |
| la contraction | a muscle becoming shorter/tighter as it acts |
| le relâchement | a muscle relaxing |
| la flexion | bending the arm |
| l’extension | straightening the arm |
| le biceps | the muscle at the front of the upper arm |
| le triceps | the muscle at the back of the upper arm |

Teacher review is required for terminology against the exact school glossary before release.

## 3. Lesson sequence and original narration draft

Target duration: 4–5 minutes including learner pauses and checks. Narration below is newly authored for this pilot.

### Beat 1 — Observe the movement (hook, 25–35 s)

**Visual:** A simple original arm model in side view. The forearm bends slowly; no muscle labels yet.

**Narration:**
« Plie doucement ton bras, puis tends-le. Tu viens de faire deux mouvements : la flexion et l’extension. Mais une question se pose : qu’est-ce qui fait bouger les os de ton bras ? Aujourd’hui, nous allons observer les muscles qui travaillent autour du coude. »

**Learner action:** Pause and try the movement gently. No force or exercise repetition required.

### Beat 2 — The parts that work together (35–45 s)

**Visual:** Original schematic: upper-arm bone, forearm bones, elbow articulation and two simplified muscle bands. Labels appear one at a time.

**Narration:**
« Les os donnent au corps une structure solide. Les muscles sont reliés aux os et les font bouger en tirant sur eux. Le coude est une articulation : c’est l’endroit où les os se rencontrent et où le bras peut se plier ou se tendre. »

**Teaching note:** Keep the drawing schematic, not anatomical medical advice. Do not imply that muscles push bones.

### Beat 3 — Flexion: bend the arm (40–50 s)

**Visual:** Forearm rotates upward. The biceps visibly shortens/thickens in a simplified diagram; the triceps relaxes. Labels: biceps / se contracte; triceps / se relâche.

**Narration:**
« Quand tu plies le bras, tu fais une flexion. Le biceps, situé à l’avant du bras, se contracte. En même temps, le triceps, situé à l’arrière, se relâche. Le travail de ces muscles permet à l’avant-bras de se rapprocher du bras. »

### Beat 4 — Extension: straighten the arm (40–50 s)

**Visual:** Forearm rotates down to a straight position. The triceps shortens/thickens in the simplified diagram; the biceps relaxes. Labels swap state.

**Narration:**
« Maintenant, tends le bras : c’est l’extension. Cette fois, le triceps se contracte et le biceps se relâche. Les deux muscles ont donc des rôles opposés dans ces deux mouvements. »

### Beat 5 — Compare and explain (30–40 s)

**Visual:** Split-screen comparison with two clear arm poses and a two-row state table. Animate only the active muscle state; keep the elbow pivot fixed.

**Narration:**
« Observe bien : pour plier le bras, le biceps se contracte. Pour le tendre, c’est le triceps qui se contracte. Les muscles tirent sur les os ; ils ne les poussent pas. Tu peux maintenant expliquer ce qui change quand ton bras bouge. »

### Beat 6 — Retrieval and mastery check (45–60 s)

**Visual:** The arm freezes at each pose. Learner selects or taps the active muscle; the feedback animates the correct state.

**Narration:**
« À toi de vérifier ce que tu as compris. Regarde le mouvement, réfléchis, puis choisis la bonne réponse. »

## 4. Assessment specification

| Item | Prompt | Correct response | Misconception targeted |
|---|---|---|---|
| Q1 | Quand le bras se plie, quel muscle se contracte ? | Le biceps | Confusing the front and back muscles |
| Q2 | Quand le bras se tend, quel muscle se contracte ? | Le triceps | Assuming the same muscle contracts for both movements |
| Q3 | Comment les muscles font-ils bouger les os ? | En tirant sur les os | Believing muscles push bones |
| Q4 | Comment appelle-t-on l’endroit où les os se rencontrent et permettent le mouvement ? | Une articulation | Confusing a muscle with a joint |

### Feedback rules

- Correct: explain why the answer matches the visible movement; replay the relevant beat once.
- Incorrect Q1/Q2: freeze the arm, highlight the front/back muscle, replay the contraction comparison, then retry with a different pose.
- Incorrect Q3: animate a pull arrow from muscle to bone; explicitly contrast pulling with pushing.
- Incorrect Q4: highlight the elbow pivot and distinguish it from the muscle tissue.
- Never mark an answer correct based on fuzzy string matching. Normalize accents/spacing only where safe; accept only the reviewed answer set.

## 5. Visual and interaction requirements

- Original vector/SVG or canvas diagram created for this lesson; no scanned textbook figure.
- Stable front/back orientation and consistent labels across every beat.
- The elbow pivot remains fixed while the forearm rotates.
- Muscle state must agree with the narration at every frame.
- Do not depict a muscle physically pushing a bone.
- Tap targets must work on a narrow Android portrait viewport.
- Include captions, replay, pause, seek and a visible progress indicator.
- Provide a reduced-motion fallback and meaningful text alternative for the diagram.

## 6. QA gates

### Scientific
- [ ] A science reviewer confirms the simplified biceps/triceps model and all narration.
- [ ] Contraction/relaxation states are correct in every animation frame.
- [ ] No misleading depiction of muscle-to-bone action.
- [ ] The joint is correctly represented as the meeting/movement point of bones.

### Curriculum and language
- [ ] Teacher confirms this bounded lesson is appropriate for the assigned Grade 5 French Science sequence.
- [ ] All vocabulary is checked against the school glossary.
- [ ] French grammar, pronunciation and captions are reviewed by a fluent French reviewer.
- [ ] No unsupported claim that this is the complete chapter or official Ministry lesson.

### Pedagogy
- [ ] Every stated objective appears in both instruction and assessment.
- [ ] Learner has a chance to predict/observe before the explanation.
- [ ] Feedback teaches the reason, not only “correct/incorrect”.
- [ ] Answer key and misconception remediation are independently checked.

### Technical
- [ ] Beat replay and seeking reproduce the same visual state.
- [ ] Audio/caption word timing remains aligned.
- [ ] Questions work with touch and keyboard.
- [ ] Portrait and landscape Android layouts are readable.
- [ ] Browser console/network checks have no unexplained errors.
- [ ] Static package has no external runtime dependency other than any explicitly approved narration delivery.

## 7. Open gates

- This is a blueprint, not a generated or playable lesson.
- The exact school assignment and canonical source-edition identity remain unverified.
- The source PDF's reproduction restriction means no source pages, figures, wording or exercises may be republished. Obtain rights advice/permission before any adaptation that reproduces protected expression.
- Papermorph has not been approved or used to generate this lesson.
- Arabic player support does not satisfy this lesson's French instructional-language requirement; French narration and terminology are the pilot acceptance target.
- No audio, animation, browser or phone test has run yet.
