"""Paginated scene/shot requirement review contracts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.api.assets.schemas import MediaType
from app.api.production_structure.schemas import LockResponse
from app.api.workspace.schemas import Page, ProductionResponse


class NodeLabel(BaseModel):
    id: UUID
    name: str
    position: int


class RequirementLabel(NodeLabel):
    media_type: MediaType


class SelectedAsset(BaseModel):
    id: UUID
    name: str
    reference: str


Readiness = Literal["READY", "MISSING", "REVIEW", "UNPLANNED"]


class EditorRow(BaseModel):
    sequence: NodeLabel
    scene: NodeLabel
    shot: NodeLabel
    requirement: RequirementLabel | None
    selected_asset: SelectedAsset | None
    locked_asset: LockResponse | None
    status: Readiness
    reason: str


class EditorPage(Page[EditorRow]):
    production: ProductionResponse
