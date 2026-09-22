"""Production hierarchy API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.assets.schemas import Description, MediaType, Name
from app.api.workspace.schemas import ProductionStatus


class ProductionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    description: Description | None = None
    status: ProductionStatus = "draft"


class NodeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    description: Description | None = None
    position: int = Field(ge=1, le=2147483647, strict=True)


class RequirementCreate(NodeCreate):
    media_type: MediaType


class NodeResponse(NodeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class SequenceResponse(NodeResponse):
    production_id: UUID


class SceneResponse(NodeResponse):
    sequence_id: UUID


class ShotResponse(NodeResponse):
    scene_id: UUID


class RequirementResponse(NodeResponse):
    shot_id: UUID
    media_type: MediaType


class LockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: UUID


class LockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    required_asset_id: UUID
    asset_id: UUID
    checksum: str
    storage_uri: str
    locked_at: datetime


class PlanningErrorDetail(BaseModel):
    code: str
    message: str


class PlanningErrorResponse(BaseModel):
    detail: PlanningErrorDetail
