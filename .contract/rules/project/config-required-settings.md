---
id: config-required-settings
title: FLASK_SECRET_KEY and DATABASE_URL are required, with no defaults
scope: [global]
impact: CRITICAL
triggers: [secret key, FLASK_SECRET_KEY, DATABASE_URL, environment variable, env, .env, config, settings, sqlite, postgres, psycopg2, driver]
appliesTo:
  - interview_app/__init__.py
  - .env.example
---

`create_app()` refuses to start unless both `FLASK_SECRET_KEY` and `DATABASE_URL` are set,
and names the missing ones. There is no `"dev"` secret and no fallback database: a forgotten
secret lets anyone forge a login session, and a forgotten URL silently starts on an empty
database. Developers set both in their own `.env` (see `.env.example`).

- A relative SQLite path (`sqlite:///data/app.db`) resolves from the project folder.
- `postgres://` and `postgresql://` URLs are rewritten to `postgresql+psycopg2://`, because the
  newest SQLAlchemy defaults to the `psycopg` driver and we ship `psycopg2-binary`.
- Never read, print or commit `.env`. Never commit a real key.

**Never:**

```python
secret = os.getenv("FLASK_SECRET_KEY", "dev")  # a default is the bug
```

Source: [ADR 0008](../../../docs/adr/0008-require-the-secret-key-and-the-database-url-with-no-defaults.md),
[ADR 0009](../../../docs/adr/0009-name-the-psycopg2-driver-and-pin-python-3-13.md)
