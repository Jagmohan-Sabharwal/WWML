"""Validated query parameters and documented workspace responses."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ProductionStatus = Literal["draft", "in_production", "completed", "archived"]
SyncStatus = Literal[
    "pending", "running", "completed", "completed_with_errors", "failed"
]


class PageQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1, le=1_000_000)
    page_size: int = Field(default=20, ge=1, le=100)


class ProductionQuery(PageQuery):
    status: ProductionStatus | None = None


class SyncQuery(PageQuery):
    status: SyncStatus | None = None


class ProductionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    status: ProductionStatus
    created_at: datetime
    updated_at: datetime


class SyncJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: SyncStatus
    started_at: datetime | None
    completed_at: datetime | None
    files_scanned: int
    files_imported: int
    files_skipped: int
    errors: list[dict[str, str]]


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class MediaStatistics(BaseModel):
    count: int = 0
    size_bytes: int = 0


class AssetStatistics(BaseModel):
    total_assets: int
    total_size_bytes: int
    by_media_type: dict[str, MediaStatistics]


class StatusStatistics(BaseModel):
    total: int
    by_status: dict[str, int]


class DashboardResponse(BaseModel):
    assets: AssetStatistics
    productions: StatusStatistics
    sync_jobs: StatusStatistics
