---
id: global-pr
title: Open a PR only when asked, with a Conventional title
scope: [global]
impact: HIGH
triggers: [pull request, open pr, raise pr, pr title, pr body, merge]
appliesTo: []
---

Open a pull request only when the user asks, with `gh pr create`, from a branch (never from
`main`). Push the branch only, never `main`.

**Title format:** the same Conventional subject a commit uses (see `global-commit`):

```
feat(app): add own questions to the interview page
```

The title is not cosmetic. On a squash merge GitHub uses the **PR title** as the commit
subject whenever the branch holds more than one commit, so a non-Conventional title lands a
non-Conventional commit on `main`. `.github/workflows/pr-title.yml` checks the title on open
and on every edit, with the same validator as the `commit-msg` hook.

**Description:** what changed, why, and how it was verified (a short test plan). Mention
anything the reviewer must know that the diff does not show. Never add an AI attribution
line or `Co-Authored-By`.

After opening the PR, report its link. Do not merge it unless asked. Do not poll CI in a loop;
read the result once and report it.

Source: [ADR 0002](../../../docs/adr/0002-use-one-conventional-format-for-commits-and-pr-titles.md)
