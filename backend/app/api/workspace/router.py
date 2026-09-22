"""Read-only workspace APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.workspace.repository import WorkspaceRepository
from app.api.workspace.schemas import (
    AssetStatistics,
    DashboardResponse,
    Page,
    ProductionQuery,
    ProductionResponse,
    SyncJobResponse,
    SyncQuery,
)
from app.api.workspace.service import WorkspaceService
from app.db.session import get_session

router = APIRouter(prefix="/api/v1", tags=["workspace"])


def get_workspace_service(
    session: Annotated[Session, Depends(get_session)],
) -> WorkspaceService:
    return WorkspaceService(WorkspaceRepository(session))


Service = Annotated[WorkspaceService, Depends(get_workspace_service)]


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(service: Service) -> DashboardResponse:
    """Aggregate active assets and all persisted production/sync statuses."""
    return service.dashboard()


@router.get("/assets/statistics", response_model=AssetStatistics, tags=["assets"])
def asset_statistics(service: Service) -> AssetStatistics:
    """Count active registrations and logical bytes, grouped by media type."""
    return service.asset_statistics()


@router.get("/productions", response_model=Page[ProductionResponse])
def productions(
    query: Annotated[ProductionQuery, Query()], service: Service
) -> Page[ProductionResponse]:
    """Filter by status; newest created first, UUID descending breaks ties."""
    return service.productions(query)


@router.get("/sync/jobs", response_model=Page[SyncJobResponse])
def sync_jobs(
    query: Annotated[SyncQuery, Query()], service: Service
) -> Page[SyncJobResponse]:
    """Newest start first, pending last; UUID descending breaks ties."""
    return service.sync_jobs(query)
