# 0002. Use one Conventional format for commits and PR titles, and enforce it

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| PR | - |
| Supersedes | - |

## Context

Commit messages so far were free-form sentences ("Add CI workflow and a Development section").
GitHub's squash merge uses the commit subject when a branch has one commit and the **PR title**
when it has several, so an unchecked PR title silently becomes the commit message on `main`.
An instruction that nothing checks only holds as well as whoever, or whatever, happens to read
it that day.

## Decision

Commit subjects and PR titles use `{type}({scope}): {description}`, with the types and scopes
listed in `.contract/project.config.json`. One validator, `tools/commit/validate_message.py`,
enforces it in two places: the `commit-msg` hook on every local commit, and
`.github/workflows/pr-title.yml` on the PR title, on open and on every edit. The vocabulary is
read from the config, so the rule text and the check cannot disagree.

## Alternatives considered

- **Enforce commits only.** Leaves the multi-commit squash path unguarded, which is the one
  that produces drift.
- **commitlint.** A second toolchain and a second copy of the vocabulary for a check that is one
  regular expression.
- **A ticket suffix such as (ABC-123).** There is no ticket tracker in this project, so there
  is nothing to link.

## Consequences

- `main`'s history becomes uniformly parseable, which any future changelog needs.
- Hooks can be skipped with `--no-verify` and `SKIP_COMMIT_LINT=1` exists for a commit that
  cannot take the format. The PR title check cannot be skipped, which is the half that reaches
  `main`.
- Existing history keeps its old style; the rule applies from now on.
