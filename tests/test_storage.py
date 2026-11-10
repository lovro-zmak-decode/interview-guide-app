import pytest

import app as app_module
from interview_app import storage
from interview_app.models import StoredFile, db
from interview_app.storage import DatabaseFileStorage, FileStorage, get_storage


def test_files_round_trip_through_the_database_backend():
    data = bytes(range(256)) * 4  # binary content including null bytes
    with app_module.app.app_context():
        get_storage().save("guides/1/cv.pdf", data, "application/pdf")
        db.session.commit()
        assert get_storage().load("guides/1/cv.pdf") == data
        row = StoredFile.query.filter_by(key="guides/1/cv.pdf").one()
        assert (row.content_type, row.size) == ("application/pdf", len(data))


def test_saving_again_replaces_the_file():
    with app_module.app.app_context():
        get_storage().save("k", b"first", "text/plain")
        db.session.commit()
        get_storage().save("k", b"second", "text/plain")
        db.session.commit()
        assert get_storage().load("k") == b"second"
        assert StoredFile.query.count() == 1


def test_missing_files_load_as_none_and_deleting_them_is_not_an_error():
    with app_module.app.app_context():
        assert get_storage().load("nope") is None
        get_storage().delete("nope")


def test_delete_removes_only_that_file():
    with app_module.app.app_context():
        get_storage().save("a", b"1", "text/plain")
        get_storage().save("b", b"2", "text/plain")
        db.session.commit()
        get_storage().delete("a")
        db.session.commit()
        assert get_storage().load("a") is None
        assert get_storage().load("b") == b"2"


def test_the_default_backend_is_the_database(monkeypatch):
    monkeypatch.delenv("FILE_STORAGE", raising=False)
    assert isinstance(get_storage(), DatabaseFileStorage)


def test_an_unknown_backend_is_rejected(monkeypatch):
    monkeypatch.setenv("FILE_STORAGE", "tape-drive")
    with pytest.raises(RuntimeError, match="tape-drive"):
        get_storage()


def test_another_backend_can_be_plugged_in(monkeypatch):
    class MemoryStorage(FileStorage):
        files: dict[str, bytes] = {}

        def save(self, key, data, content_type):
            self.files[key] = data

        def load(self, key):
            return self.files.get(key)

        def delete(self, key):
            self.files.pop(key, None)

    monkeypatch.setitem(storage._BACKENDS, "memory", MemoryStorage)
    monkeypatch.setenv("FILE_STORAGE", "memory")
    with app_module.app.app_context():
        get_storage().save("k", b"in memory", "text/plain")
        assert get_storage().load("k") == b"in memory"
        assert StoredFile.query.count() == 0
