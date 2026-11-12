# 0013. Run CI as two jobs, on SQLite and PostgreSQL, with pinned actions

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| PR | [#6](https://github.com/lovro-zmak-decode/interview-guide-app/pull/6) |
| Supersedes | - |

## Context

There was no CI, no linter and no tests. The first deployment target, PostgreSQL on Railway,
surfaced a driver problem that SQLite-only checks would never have found. GitHub bills every job
as a whole minute, so one job per check costs more than the checks themselves.

## Decision

`.github/workflows/ci.yml` has two jobs. `checks` runs lint, format check, type check and the
tests on SQLite in sequence. `tests-postgres` runs the same tests against a PostgreSQL service.
The test suite picks its database from `TEST_DATABASE_URL`. Every action is pinned to a commit
SHA, with the tag in a comment, and Dependabot bumps them.

## Alternatives considered

- **One job per check.** Faster wall clock, several times the billable minutes.
- **SQLite only.** Misses database-specific behaviour.

## Consequences

- A pull request that breaks either database fails its check.
- The suite empties and recreates tables for every test, so `TEST_DATABASE_URL` must point at a
  scratch database.
- Branch protection (requiring the check) is a repository setting and is not part of this
  decision.
