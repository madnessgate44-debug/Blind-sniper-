---
name: scope-discipline
description: "This skill should be used when fixing a bug, making a change, or reviewing a diff, and when tempted to refactor, clean up or add features that were not requested."
triggers:
- fix
- bug
- refactor
- minimal change
- scope
- simplify
---

# Scope Discipline

Do the smallest change that solves the stated problem.

Before writing code, stop at the first rung that holds:

1. Does this need to exist at all? If not, say so.
2. Does the standard library already do it? Use it.
3. Does a native platform or browser feature cover it? Use it.
4. Does an already-installed dependency solve it? Use it.
5. Can it be one line? Make it one line.
6. Only then write the minimum that works.

Always:

- Find the root cause before touching anything.
- Fix only the specific issue. Never refactor or "improve" unrelated code.
- Show exactly what changed and why.
- If a fix breaks something else, say so immediately and trace the cause.
- Mark an intentional simplification with a `ponytail:` comment naming the upgrade path.
- Mark a deliberate deferral with `operator:` and a one-line reason. List all deferrals in the PR body under `Deferred`.

Never skip: input validation at trust boundaries, error handling that prevents data loss, security, and anything the owner explicitly asked for.
