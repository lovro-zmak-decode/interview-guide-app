"""
Lets one process at a time prepare the database at start-up.

gunicorn starts several workers and each one imports the app, which creates the
tables. On a brand-new database two workers can both see "no tables yet", and
the second CREATE TABLE then fails with "already exists" and takes that worker
down. Taking a PostgreSQL advisory lock around the set-up makes the second
worker wait until the first has finished; it then finds the tables in place and
has nothing left to do. The lock belongs to the database connection, so it is
released even if the process holding it dies.

Other databases (the local SQLite file) are used by a single process, so there
the lock does nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Any number works, as long as nothing else in this database uses the same one.
_LOCK_KEY = 7_201_948_331


@contextmanager
def startup_lock(engine: Engine) -> Iterator[None]:
    if engine.dialect.name != "postgresql":
        yield
        return
    # Autocommit, so the connection does not sit in an open transaction while it waits.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": _LOCK_KEY})
        try:
            yield
        finally:
            # Unlock explicitly: a pooled connection keeps its session-level locks.
            conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK_KEY})
