# 0008. Require FLASK_SECRET_KEY and DATABASE_URL, with no defaults

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| PR | [#4](https://github.com/lovro-zmak-decode/interview-guide-app/pull/4) |
| Supersedes | - |

## Context

The app fell back to the secret `"dev"` and to a local SQLite file when nothing was set. That is
convenient locally and dangerous in production: a forgotten secret lets anyone forge a login
session, and a forgotten database URL silently starts on an empty database. An earlier version
only required the secret when `DATABASE_URL` was present, which still allowed running with the
development secret locally.

## Decision

`create_app()` refuses to start unless both variables are set, and says which are missing.
Developers put both in their own `.env`; `.env.example` shows how. A relative SQLite path such
as `sqlite:///data/app.db` is resolved from the project folder.

## Consequences

- A misconfigured deployment fails at start-up instead of running unsafely.
- Every developer and every test run must supply both values (the test setup does).
- Existing local setups need two lines added to `.env` once.
