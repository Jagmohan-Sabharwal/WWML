"""Read-only editor handoff, based on production planning and locked assets."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.editor.repository import EditorRepository
from app.api.editor.schemas import EditorPage
from app.api.editor.service import EditorService
from app.api.production_structure.schemas import PlanningErrorResponse
from app.api.workspace.schemas import PageQuery
from app.db.session import get_session

router = APIRouter(prefix="/api/v1/productions", tags=["editor"])


def get_editor_service(
    session: Annotated[Session, Depends(get_session)],
) -> EditorService:
    return EditorService(EditorRepository(session))


@router.get(
    "/{production_id}/editor",
    response_model=EditorPage,
    responses={404: {"model": PlanningErrorResponse}},
)
def review(
    production_id: UUID,
    query: Annotated[PageQuery, Query()],
    service: Annotated[EditorService, Depends(get_editor_service)],
) -> EditorPage:
    """Review requirement rows and unplanned shots; no file bytes are verified."""
    return service.review(production_id, query)
