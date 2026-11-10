import os

import pytest

from interview_app import create_app

REQUIRED = ("FLASK_SECRET_KEY", "DATABASE_URL")
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_refuses_to_start_without_the_required_settings(monkeypatch):
    for name in REQUIRED:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError) as error:
        create_app()
    assert "FLASK_SECRET_KEY" in str(error.value)
    assert "DATABASE_URL" in str(error.value)


@pytest.mark.parametrize("missing", REQUIRED)
def test_names_the_setting_that_is_missing(monkeypatch, missing):
    monkeypatch.setenv("FLASK_SECRET_KEY", "secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/unused.db")
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError, match=missing):
        create_app()


def test_uses_the_configured_secret_key(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "my-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/unused.db")
    assert create_app().secret_key == "my-secret"


@pytest.mark.parametrize("scheme", ["postgres", "postgresql"])
def test_postgres_urls_name_the_psycopg2_driver(monkeypatch, scheme):
    monkeypatch.setenv("DATABASE_URL", f"{scheme}://user:pw@localhost:5432/db")
    assert create_app().config["SQLALCHEMY_DATABASE_URI"] == "postgresql+psycopg2://user:pw@localhost:5432/db"


def test_relative_sqlite_path_is_resolved_from_the_project_folder(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/app.db")
    uri = create_app().config["SQLALCHEMY_DATABASE_URI"]
    assert uri == f"sqlite:///{PROJECT_DIR}/data/app.db"


def test_absolute_sqlite_path_is_kept(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/x.db")
    assert create_app().config["SQLALCHEMY_DATABASE_URI"] == f"sqlite:///{tmp_path}/x.db"
