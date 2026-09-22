"""Workspace contracts without external services."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.workspace.repository import WorkspaceRepository
from app.api.workspace.router import get_workspace_service
from app.api.workspace.service import WorkspaceService
from app.main import create_app


@pytest.fixture
def workspace():
    repository = Mock(spec=WorkspaceRepository)
    repository.asset_groups.return_value = []
    repository.production_counts.return_value = {}
    repository.sync_counts.return_value = {}
    repository.productions.return_value = ([], 0)
    repository.sync_jobs.return_value = ([], 0)
    app = create_app()
    app.dependency_overrides[get_workspace_service] = lambda: WorkspaceService(
        repository
    )
    with TestClient(app) as client:
        yield client, repository


def test_empty_dashboard(workspace):
    client, _ = workspace
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["assets"]["total_assets"] == 0
    assert len(body["assets"]["by_media_type"]) == 5
    assert body["productions"]["by_status"]["draft"] == 0
    assert body["sync_jobs"]["by_status"]["pending"] == 0


def test_statistics_route_and_totals(workspace):
    client, repository = workspace
    repository.asset_groups.return_value = [("video", 2, 300), ("audio", 1, 50)]
    response = client.get("/api/v1/assets/statistics")
    assert response.status_code == 200
    assert response.json()["total_assets"] == 3
    assert response.json()["total_size_bytes"] == 350


@pytest.mark.parametrize("path", ["/productions", "/sync/jobs"])
@pytest.mark.parametrize(
    "query", ["page=0", "page_size=101", "status=invalid", "unknown=1"]
)
def test_invalid_query(workspace, path, query):
    client, repository = workspace
    assert client.get(f"/api/v1{path}?{query}").status_code == 422
    repository.productions.assert_not_called()
    repository.sync_jobs.assert_not_called()


@pytest.mark.parametrize(
    "path,method", [("/productions", "productions"), ("/sync/jobs", "sync_jobs")]
)
def test_out_of_range_page(workspace, path, method):
    client, repository = workspace
    getattr(repository, method).return_value = ([], 21)
    response = client.get(f"/api/v1{path}?page=5&page_size=10")
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 21,
        "page": 5,
        "page_size": 10,
        "total_pages": 3,
    }


def test_openapi(workspace):
    client, _ = workspace
    paths = client.get("/openapi.json").json()["paths"]
    for path in ("/dashboard", "/productions", "/sync/jobs", "/assets/statistics"):
        operation = paths[f"/api/v1{path}"]["get"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"]
