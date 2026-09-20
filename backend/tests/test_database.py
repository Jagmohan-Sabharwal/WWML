"""Session ownership, safe URLs and migration SQL without external services."""

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import make_url
from starlette.requests import Request

from alembic import command
from app.core.config import Settings
from app.db.session import database_url, get_session
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def test_password_special_characters_round_trip() -> None:
    secret = "p@ss:/?#%word"
    url = database_url(Settings(_env_file=None, postgres_password=secret))
    assert make_url(url.render_as_string(hide_password=False)).password == secret
    assert secret not in str(url)
    assert url.drivername == "postgresql+psycopg"


def test_session_closes_and_does_not_commit_implicitly() -> None:
    app = create_app(Settings(_env_file=None))
    factory = MagicMock()
    app.state.session_factory = factory
    request = Request({"type": "http", "app": app})
    dependency = get_session(request)
    session = next(dependency)
    with pytest.raises(StopIteration):
        next(dependency)
    session.commit.assert_not_called()
    factory.return_value.__exit__.assert_called_once()


def test_session_rolls_back_on_failure() -> None:
    app = create_app(Settings(_env_file=None))
    factory = MagicMock()
    app.state.session_factory = factory
    dependency = get_session(Request({"type": "http", "app": app}))
    session = next(dependency)
    with pytest.raises(RuntimeError, match="failed"):
        dependency.throw(RuntimeError("failed"))
    session.rollback.assert_called_once()
    factory.return_value.__exit__.assert_called_once()


def test_engine_is_disposed_on_application_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock()
    monkeypatch.setattr("app.main.create_database_engine", lambda settings: engine)
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert client.get("/health").status_code == 200
        engine.connect.assert_not_called()
    engine.dispose.assert_called_once()


def test_offline_migration_has_assets_and_no_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = str(uuid4())
    monkeypatch.setenv("POSTGRES_PASSWORD", secret)
    output = StringIO()
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE assets" in sql
    assert "uq_assets_sha256" in sql
    assert secret not in sql
