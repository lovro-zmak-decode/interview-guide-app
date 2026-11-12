---
id: style-principles
title: KISS, DRY, YAGNI, and remove dead code
scope: [global]
impact: MEDIUM
triggers: [kiss, dry, yagni, abstraction, dead code, refactor, simplicity, comment]
appliesTo: []
---

- **KISS.** Prefer simple, readable code over clever abstractions. One clear purpose per
  module or function.
- **DRY.** Extract repeated logic only when it appears in three or more places and the
  abstraction is clearly stable.
- **YAGNI.** Do not build for hypothetical future requirements. Remove dead code promptly.
- Do only what the task asks. No drive-by refactors of unrelated code.
- Default to no comments. Add one only when the why is non-obvious: a hidden constraint, a
  workaround for a specific bug, behaviour that would surprise a reader. Never narrate what
  the code does, and never write a multi-line docstring.

Source: [CLAUDE.md](../../../CLAUDE.md)
