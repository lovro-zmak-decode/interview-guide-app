"""
Where uploaded files (a candidate's CV and LinkedIn export) are kept.

The rest of the app only uses the small FileStorage interface below and never
the database table behind it. By default files live in the database
(FILE_STORAGE=database), so a deployment needs no external storage.

To move to S3 or similar later: add a class with the same three methods,
register it in _BACKENDS and set FILE_STORAGE. Nothing else has to change,
because documents are referenced by a storage key (see models.GuideDocument).
The database backend does not commit; callers commit together with their own
changes, so a file and its metadata are saved or lost together.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from .models import StoredFile, db


class FileStorage(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes, content_type: str) -> None:
        """Store `data` under `key`, replacing anything already there."""

    @abstractmethod
    def load(self, key: str) -> bytes | None:
        """The bytes stored under `key`, or None if there is nothing."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove `key`. Not an error if it does not exist."""


class DatabaseFileStorage(FileStorage):
    def save(self, key: str, data: bytes, content_type: str) -> None:
        row = StoredFile.query.filter_by(key=key).first()
        if row is None:
            row = StoredFile(key=key)
            db.session.add(row)
        row.content_type = content_type
        row.data = data
        row.size = len(data)

    def load(self, key: str) -> bytes | None:
        row = StoredFile.query.filter_by(key=key).first()
        return bytes(row.data) if row else None

    def delete(self, key: str) -> None:
        StoredFile.query.filter_by(key=key).delete()


_BACKENDS = {"database": DatabaseFileStorage}


def get_storage() -> FileStorage:
    name = os.getenv("FILE_STORAGE", "database").lower()
    if name not in _BACKENDS:
        raise RuntimeError(f"Unknown FILE_STORAGE '{name}'. Available: {', '.join(_BACKENDS)}")
    return _BACKENDS[name]()
