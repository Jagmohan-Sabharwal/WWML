"""Read-only, paginated ingestion progress, documented through OpenAPI."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.drive_import import DriveImport

Status = Literal["watch", "import", "rename", "register", "done", "failed", "skipped"]
router = APIRouter(prefix="/integrations/google-drive/imports", tags=["Drive imports"])
Database = Annotated[Session, Depends(get_session)]


class ImportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    file_id: str
    source_version: str
    source_name: str
    status: Status
    attempts: int
    error_code: str | None
    asset_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ImportPage(BaseModel):
    items: list[ImportRead]
    total: int
    page: int
    page_size: int


@router.get("", response_model=ImportPage)
def list_imports(
    session: Database,
    status: Status | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ImportPage:
    statement = select(DriveImport)
    if status:
        statement = statement.where(DriveImport.status == status)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = session.scalars(
        statement.order_by(DriveImport.created_at.desc(), DriveImport.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return ImportPage(
        items=[ImportRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{import_id}",
    response_model=ImportRead,
    responses={404: {"description": "Import not found"}},
)
def get_import(import_id: UUID, session: Database) -> ImportRead:
    job = session.get(DriveImport, import_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import not found")
    return ImportRead.model_validate(job)
