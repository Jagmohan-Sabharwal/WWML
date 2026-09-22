"""Compose stable workspace response contracts from persisted data."""

from typing import get_args

from app.api.workspace.repository import WorkspaceRepository
from app.api.workspace.schemas import (
    AssetStatistics,
    DashboardResponse,
    MediaStatistics,
    Page,
    ProductionQuery,
    ProductionResponse,
    ProductionStatus,
    StatusStatistics,
    SyncJobResponse,
    SyncQuery,
    SyncStatus,
)


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository) -> None:
        self.repository = repository

    def asset_statistics(self) -> AssetStatistics:
        groups = {
            kind: MediaStatistics()
            for kind in ("video", "audio", "image", "document", "other")
        }
        for kind, count, size in self.repository.asset_groups():
            groups[kind] = MediaStatistics(count=count, size_bytes=size)
        return AssetStatistics(
            total_assets=sum(group.count for group in groups.values()),
            total_size_bytes=sum(group.size_bytes for group in groups.values()),
            by_media_type=groups,
        )

    def dashboard(self) -> DashboardResponse:
        productions = dict.fromkeys(get_args(ProductionStatus), 0)
        productions.update(self.repository.production_counts())
        jobs = dict.fromkeys(get_args(SyncStatus), 0)
        jobs.update(self.repository.sync_counts())
        return DashboardResponse(
            assets=self.asset_statistics(),
            productions=StatusStatistics(
                total=sum(productions.values()), by_status=productions
            ),
            sync_jobs=StatusStatistics(total=sum(jobs.values()), by_status=jobs),
        )

    def productions(self, query: ProductionQuery) -> Page[ProductionResponse]:
        items, total = self.repository.productions(query)
        return Page(
            items=[ProductionResponse.model_validate(item) for item in items],
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=(total + query.page_size - 1) // query.page_size,
        )

    def sync_jobs(self, query: SyncQuery) -> Page[SyncJobResponse]:
        items, total = self.repository.sync_jobs(query)
        return Page(
            items=[SyncJobResponse.model_validate(item) for item in items],
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=(total + query.page_size - 1) // query.page_size,
        )
