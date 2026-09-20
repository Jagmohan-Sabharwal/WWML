"""Documented HTTP API for registering and discovering reusable source assets."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.assets.repository import AssetRepository
from app.api.assets.schemas import (
    AssetCreate,
    AssetErrorDetail,
    AssetErrorResponse,
    AssetPage,
    AssetQuery,
    AssetResponse,
    AssetUpdate,
)
from app.api.assets.service import AssetNotFoundError, AssetService, DuplicateAssetError
from app.db.session import get_session

router = APIRouter(prefix="/assets", tags=["assets"])


def get_asset_service(
    session: Annotated[Session, Depends(get_session)],
) -> AssetService:
    return AssetService(AssetRepository(session))


Service = Annotated[AssetService, Depends(get_asset_service)]
NOT_FOUND = {"model": AssetErrorResponse, "description": "Asset ID not found"}
CONFLICT = {
    "model": AssetErrorResponse,
    "description": "Identical file already registered; reuse existing_asset_id",
}


@router.post(
    "",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an existing asset",
    responses={409: CONFLICT},
)
def create_asset(
    data: AssetCreate, response: Response, service: Service
) -> AssetResponse:
    """Register metadata, checking the checksum before creating a new record."""
    asset = service.create(data)
    response.headers["Location"] = f"/assets/{asset.id}"
    return AssetResponse.model_validate(asset)


@router.get("", response_model=AssetPage, summary="Search and filter reusable assets")
def list_assets(query: Annotated[AssetQuery, Query()], service: Service) -> AssetPage:
    """Newest first, with UUID as a stable tie-breaker; filters combine with AND."""
    return service.list(query)


@router.get(
    "/{asset_id}",
    response_model=AssetResponse,
    responses={404: NOT_FOUND},
    summary="Read an asset",
)
def get_asset(asset_id: UUID, service: Service) -> AssetResponse:
    return AssetResponse.model_validate(service.get(asset_id))


@router.patch(
    "/{asset_id}",
    response_model=AssetResponse,
    responses={404: NOT_FOUND, 409: CONFLICT},
    summary="Update asset metadata",
)
def update_asset(asset_id: UUID, data: AssetUpdate, service: Service) -> AssetResponse:
    """Unspecified fields stay unchanged. JSON metadata replaces the whole object."""
    return AssetResponse.model_validate(service.update(asset_id, data))


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: NOT_FOUND},
    summary="Delete an asset registration",
)
def delete_asset(asset_id: UUID, service: Service) -> Response:
    """Delete the database record only; the referenced source file remains intact."""
    service.delete(asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def register_assets_api(application: FastAPI) -> None:
    """Install this slice's routes and explicit, secret-free error contracts."""
    application.include_router(router)

    @application.exception_handler(AssetNotFoundError)
    async def not_found(request: Request, error: AssetNotFoundError) -> JSONResponse:
        body = AssetErrorResponse(
            detail=AssetErrorDetail(code="asset_not_found", message="Asset not found.")
        )
        return JSONResponse(status_code=404, content=body.model_dump(mode="json"))

    @application.exception_handler(DuplicateAssetError)
    async def duplicate(request: Request, error: DuplicateAssetError) -> JSONResponse:
        body = AssetErrorResponse(
            detail=AssetErrorDetail(
                code="duplicate_asset",
                message="An asset with this checksum exists; reuse the existing asset.",
                existing_asset_id=error.existing_asset_id,
            )
        )
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))
