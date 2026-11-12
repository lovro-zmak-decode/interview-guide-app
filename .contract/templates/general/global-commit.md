---
id: global-commit
title: Commit only when asked, using the Conventional format
scope: [global]
impact: HIGH
triggers: [commit, git commit, commit message, stage changes]
appliesTo: []
---

Commit only when the user asks. Never `git add` or `git commit` while on `{{protectedBranches}}`
(see `global-branching`).

Before committing, run `ruff check .`, `ruff format --check .`, `mypy` and `pytest`
(see `global-testing`), and stage any files the formatter rewrote.

**Message format:** `{type}({scope}): {description}`

- `type`: `{{branchTypes}}`
- `scope`: `{{commitScopes}}` (omit the parentheses if the change spans several)
- `description`: imperative, lowercase, no trailing period, under about 70 characters

```
feat(app): add own questions to the interview page
fix(ci): point the health check at /healthz
chore(deps): bump ruff
```

A body is allowed and encouraged when the change needs justification. Explain **why**, not
what the diff already shows. Separate it from the subject with a blank line and wrap at
78 characters.

Never include `Co-Authored-By`, AI attribution, or any reference to the tooling that
produced the change. Never use an em dash (see `style-no-em-dash`).

**The `commit-msg` hook backstops this.** It runs `tools/commit/validate_message.py`, which
reads the type and scope vocabulary from `.contract/project.config.json`, so the hook and
this rule cannot disagree. Merge, revert and autosquash (`fixup!`, `squash!`) subjects are
exempt. It is a backstop, not protection: hooks can be skipped with `--no-verify`. The PR
title follows the same format and is checked in CI (see `global-pr`).

Emergency bypass, for a commit that genuinely cannot take the format:

```bash
SKIP_COMMIT_LINT=1 git commit ...
```

Source: [ADR 0002](../../../docs/adr/0002-use-one-conventional-format-for-commits-and-pr-titles.md)
