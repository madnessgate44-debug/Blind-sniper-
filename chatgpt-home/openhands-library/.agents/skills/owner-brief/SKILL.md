---
name: owner-brief
description: "This skill should be used when writing a final report, PR summary, status update or handoff for the owner, or when the user asks for \"status\", \"what happened\", \"a summary\" or \"a brief\"."
triggers:
- final report
- status
- summary
- handoff
- brief
- what happened
---

# Owner Brief

The owner reads on a phone, is non-technical, has ADHD and cannot verify code. Reports must be skimmable in one screen.

Order, always:

1. **BLOCKER** (or "None"). One line.
2. **Changed**: PR links and one plain sentence each.
3. **Evidence**: how many claims Verified vs UNVERIFIED. List the UNVERIFIED ones.
4. **Costs and irreversible steps**: anything that costs money or is hard to undo. Skip the line if none.
5. **ONE next action** for the owner, one sentence. If a decision is needed, give at most one, with your recommendation.

Rules:

- The top part fits about 8 short lines. Put details below a line that says `Details`.
- No preamble. Do not restate the request.
- No jargon. If a term is unavoidable, explain it in five words.
- Never write "done" or "fixed" without evidence. Use Verified / Observed-not-verified / Hypothesis / Blocked.
- Never ask more than one question.
- State what you decided without asking, and why, in one line each.
- Do not claim something was or was not merged without checking the PR state through the API first.
