"""Health contracts and dependency failures must remain stable."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_health_contract_without_dependency_calls(client: TestClient) -> None:
    with (
        patch("app.db.connectivity.psycopg.connect") as postgres,
        patch("app.db.connectivity.Redis.from_url") as redis,
    ):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    postgres.assert_not_called()
    redis.assert_not_called()


@pytest.mark.parametrize(
    ("postgres", "redis", "status_code", "status"),
    [
        (True, True, 200, "ok"),
        (False, True, 503, "unavailable"),
        (True, False, 503, "unavailable"),
        (False, False, 503, "unavailable"),
    ],
)
def test_readiness_contract(
    client: TestClient, postgres: bool, redis: bool, status_code: int, status: str
) -> None:
    with (
        patch("app.api.health.service.postgres_ready", return_value=postgres),
        patch("app.api.health.service.redis_ready", return_value=redis),
    ):
        response = client.get("/health/ready")
    assert response.status_code == status_code
    assert response.json() == {
        "status": status,
        "checks": {"postgres": postgres, "redis": redis},
    }


def test_openapi_documents_health_and_unavailable(application: FastAPI) -> None:
    paths = application.openapi()["paths"]
    assert "200" in paths["/health"]["get"]["responses"]
    assert "503" in paths["/health/ready"]["get"]["responses"]
