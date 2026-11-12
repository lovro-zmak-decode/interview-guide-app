---
id: global-testing
title: Test, verify, and never weaken tests to pass
scope: [global]
impact: HIGH
triggers: [test, tests, verify, test suite, lint, typecheck, coverage, pytest, ruff, mypy]
appliesTo: []
---

- Add tests for new behaviour and for the bug you fixed. Tests live in `tests/`.
- Before committing run `ruff check .`, `ruff format --check .`, `mypy` and `pytest`.
- A change that touches queries, models or storage must also pass on PostgreSQL, because
  that is the production database: `TEST_DATABASE_URL=postgresql://user:pw@localhost:5432/scratch pytest`.
  The database is emptied for every test, so use a scratch one. CI runs both.
- **Never delete, skip or comment out a test to make a suite pass.** If a test is genuinely
  wrong, explain why instead of silently removing it.
- Tests stub the language model (the `llm` fixture). Never make a test call a real model or
  depend on a real API key.
- Verify against real behaviour, not only green tests: for a UI change start the app and use
  the feature. If a check fails, is missing, or was skipped, say so plainly with the output.
  Never report success you did not verify.

Source: [ADR 0013](../../../docs/adr/0013-run-ci-as-two-jobs-on-sqlite-and-postgresql-with-pinned-actions.md)
