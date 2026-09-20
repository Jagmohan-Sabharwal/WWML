"""Configuration precedence, validation, masking and application isolation."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def test_environment_overrides_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_NAME=From file\nPOSTGRES_PORT=5433\n", encoding="utf-8")
    monkeypatch.setenv("APP_NAME", "From environment")
    settings = Settings(_env_file=env_file)
    assert settings.app_name == "From environment"
    assert settings.postgres_port == 5433


@pytest.mark.parametrize(
    "values", [{"postgres_port": 0}, {"postgres_port": 65536}, {"log_level": "INVALID"}]
)
def test_invalid_configuration_is_rejected(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_secrets_are_masked() -> None:
    settings = Settings(
        _env_file=None,
        postgres_password="postgres-secret",
        redis_url="redis://:redis-secret@redis:6379",
    )
    for representation in (repr(settings), settings.model_dump_json()):
        assert "postgres-secret" not in representation
        assert "redis-secret" not in representation


def test_application_settings_do_not_leak_between_instances() -> None:
    first = create_app(Settings(_env_file=None, app_name="First"))
    second = create_app(Settings(_env_file=None, app_name="Second"))
    assert TestClient(first).get("/openapi.json").json()["info"]["title"] == "First"
    assert TestClient(second).get("/openapi.json").json()["info"]["title"] == "Second"
