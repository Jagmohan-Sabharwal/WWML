"""Adapter checks close connections and never leak credentials."""

import logging
from unittest.mock import patch

import psycopg
import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError

from app.core.config import Settings
from app.db.connectivity import postgres_ready, redis_ready


def test_successful_probes_close_connections(settings: Settings) -> None:
    with patch("app.db.connectivity.psycopg.connect") as connect:
        connection = connect.return_value.__enter__.return_value
        connection.execute.return_value.fetchone.return_value = (1,)
        assert postgres_ready(settings)
        connect.return_value.__exit__.assert_called_once()
        assert connect.call_args.kwargs["connect_timeout"] == 3
    with patch("app.db.connectivity.Redis.from_url") as connect:
        connect.return_value.__enter__.return_value.ping.return_value = True
        assert redis_ready(settings)
        connect.return_value.__exit__.assert_called_once()
        assert connect.call_args.kwargs["socket_timeout"] == 1


def test_missing_database_password_skips_connection() -> None:
    with patch("app.db.connectivity.psycopg.connect") as connect:
        assert not postgres_ready(Settings(_env_file=None, postgres_password=""))
        connect.assert_not_called()


def test_connection_errors_are_sanitized(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "credential-that-must-not-leak"
    logger = logging.getLogger("wwml.health")
    logger.addHandler(caplog.handler)
    with (
        patch(
            "app.db.connectivity.psycopg.connect",
            side_effect=psycopg.OperationalError(secret),
        ),
        patch(
            "app.db.connectivity.Redis.from_url", side_effect=ConnectionError(secret)
        ),
    ):
        try:
            response = client.get("/health/ready")
        finally:
            logger.removeHandler(caplog.handler)
    assert response.status_code == 503
    assert response.json()["checks"] == {"postgres": False, "redis": False}
    assert secret not in response.text
    logs = caplog.text
    assert "readiness check failed" in logs
    assert secret not in logs


def test_invalid_redis_url_reports_not_ready() -> None:
    assert not redis_ready(Settings(_env_file=None, redis_url="invalid://url"))
