# 0009. Name the psycopg2 driver and pin Python 3.13

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| PR | [#4](https://github.com/lovro-zmak-decode/interview-guide-app/pull/4) |
| Supersedes | - |

## Context

SQLAlchemy 2.1 maps `postgresql://` URLs to the newer `psycopg` driver, but the project ships
`psycopg2-binary`. The mismatch would have crashed the app at start-up on Railway with "No
module named psycopg". Railway also picks its own Python version, and the old pin
(`psycopg2-binary==2.9.9`) has no wheel for current Pythons.

## Decision

The database URL is rewritten to `postgresql+psycopg2://` for both `postgres://` and
`postgresql://`. `psycopg2-binary` is pinned to a release that supports current Pythons, and
`.python-version` pins Python 3.13, which the Nixpacks builder supports.

## Consequences

- The driver no longer depends on the SQLAlchemy default, so upgrading SQLAlchemy cannot break
  the connection.
- Moving to `psycopg` 3 later is a deliberate change of the URL prefix and the requirement.
- Local development may run a newer Python than the one Railway builds with.
