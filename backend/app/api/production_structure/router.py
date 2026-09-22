"""Create and traverse production plans; explicitly lock registry asset choices."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.production_structure.repository import PlanningRepository
from app.api.production_structure.schemas import (
    LockRequest,
    LockResponse,
    NodeCreate,
    PlanningErrorResponse,
    ProductionCreate,
    RequirementCreate,
    RequirementResponse,
    SceneResponse,
    SequenceResponse,
    ShotResponse,
)
from app.api.production_structure.service import PlanningError, PlanningService
from app.api.workspace.schemas import Page, PageQuery, ProductionResponse
from app.db.session import get_session
from app.models import Production
from app.models.production_structure import (
    LockedAsset,
    ProductionSequence,
    RequiredAsset,
    Scene,
    Shot,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["production planning"],
    responses={
        404: {"model": PlanningErrorResponse, "description": "Record not found"},
        409: {
            "model": PlanningErrorResponse,
            "description": "Position or selection conflict",
        },
    },
)


def get_planning_service(
    session: Annotated[Session, Depends(get_session)],
) -> PlanningService:
    return PlanningService(PlanningRepository(session))


Service = Annotated[PlanningService, Depends(get_planning_service)]


@router.post("/productions", response_model=ProductionResponse, status_code=201)
def create_production(data: ProductionCreate, service: Service) -> ProductionResponse:
    """Start a persisted documentary production."""
    return ProductionResponse.model_validate(
        service.create(Production(**data.model_dump()))
    )


@router.get("/productions/{production_id}", response_model=ProductionResponse)
def get_production(production_id: UUID, service: Service) -> ProductionResponse:
    return ProductionResponse.model_validate(service.require(Production, production_id))


@router.post(
    "/productions/{production_id}/sequences",
    response_model=SequenceResponse,
    status_code=201,
)
def create_production_sequence(
    production_id: UUID, data: NodeCreate, service: Service
) -> SequenceResponse:
    """Create a child with an explicit, unique positive sibling position."""
    service.require(Production, production_id)
    row = service.create(
        ProductionSequence(production_id=production_id, **data.model_dump())
    )
    return SequenceResponse.model_validate(row)


@router.get(
    "/productions/{production_id}/sequences", response_model=Page[SequenceResponse]
)
def list_production_sequence(
    production_id: UUID,
    query: Annotated[PageQuery, Query()],
    service: Service,
) -> Page[SequenceResponse]:
    """List only this parent's children, ordered by position with bounded pagination."""
    service.require(Production, production_id)
    return service.children(
        ProductionSequence,
        ProductionSequence.production_id,
        production_id,
        query,
        SequenceResponse,
    )


@router.post(
    "/sequences/{sequence_id}/scenes", response_model=SceneResponse, status_code=201
)
def create_scene(
    sequence_id: UUID, data: NodeCreate, service: Service
) -> SceneResponse:
    """Create a child with an explicit, unique positive sibling position."""
    service.require(ProductionSequence, sequence_id)
    row = service.create(Scene(sequence_id=sequence_id, **data.model_dump()))
    return SceneResponse.model_validate(row)


@router.get("/sequences/{sequence_id}/scenes", response_model=Page[SceneResponse])
def list_scene(
    sequence_id: UUID,
    query: Annotated[PageQuery, Query()],
    service: Service,
) -> Page[SceneResponse]:
    """List only this parent's children, ordered by position with bounded pagination."""
    service.require(ProductionSequence, sequence_id)
    return service.children(Scene, Scene.sequence_id, sequence_id, query, SceneResponse)


@router.post("/scenes/{scene_id}/shots", response_model=ShotResponse, status_code=201)
def create_shot(scene_id: UUID, data: NodeCreate, service: Service) -> ShotResponse:
    """Create a child with an explicit, unique positive sibling position."""
    service.require(Scene, scene_id)
    row = service.create(Shot(scene_id=scene_id, **data.model_dump()))
    return ShotResponse.model_validate(row)


@router.get("/scenes/{scene_id}/shots", response_model=Page[ShotResponse])
def list_shot(
    scene_id: UUID,
    query: Annotated[PageQuery, Query()],
    service: Service,
) -> Page[ShotResponse]:
    """List only this parent's children, ordered by position with bounded pagination."""
    service.require(Scene, scene_id)
    return service.children(Shot, Shot.scene_id, scene_id, query, ShotResponse)


@router.post(
    "/shots/{shot_id}/required-assets",
    response_model=RequirementResponse,
    status_code=201,
)
def create_required_asset(
    shot_id: UUID, data: RequirementCreate, service: Service
) -> RequirementResponse:
    """Create a child with an explicit, unique positive sibling position."""
    service.require(Shot, shot_id)
    row = service.create(RequiredAsset(shot_id=shot_id, **data.model_dump()))
    return RequirementResponse.model_validate(row)


@router.get(
    "/shots/{shot_id}/required-assets", response_model=Page[RequirementResponse]
)
def list_required_asset(
    shot_id: UUID,
    query: Annotated[PageQuery, Query()],
    service: Service,
) -> Page[RequirementResponse]:
    """List only this parent's children, ordered by position with bounded pagination."""
    service.require(Shot, shot_id)
    return service.children(
        RequiredAsset, RequiredAsset.shot_id, shot_id, query, RequirementResponse
    )


@router.put(
    "/required-assets/{requirement_id}/locked-asset", response_model=LockResponse
)
def lock_asset(
    requirement_id: UUID, data: LockRequest, service: Service
) -> LockResponse:
    """Select an active matching asset; repeating the same choice is idempotent."""
    return LockResponse.model_validate(service.lock(requirement_id, data.asset_id))


@router.get(
    "/required-assets/{requirement_id}/locked-asset", response_model=LockResponse
)
def get_lock(requirement_id: UUID, service: Service) -> LockResponse:
    """Read the selected file snapshot, including after registry soft deletion."""
    service.require(RequiredAsset, requirement_id)
    return LockResponse.model_validate(service.require(LockedAsset, requirement_id))


@router.delete("/required-assets/{requirement_id}/locked-asset", status_code=204)
def unlock_asset(requirement_id: UUID, service: Service) -> Response:
    """Explicitly release a selection; retain the requirement and registry asset."""
    service.unlock(requirement_id)
    return Response(status_code=204)


def register_planning_api(application: FastAPI) -> None:
    application.include_router(router)

    @application.exception_handler(PlanningError)
    async def planning_error(request: Request, error: PlanningError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status,
            content={"detail": {"code": error.code, "message": str(error)}},
        )
