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

router = APIRouter(tags=["assets"])


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
    data: AssetCreate, request: Request, response: Response, service: Service
) -> AssetResponse:
    """Register metadata, checking the checksum before creating a new record."""
    asset = service.create(data)
    base_path = request.url.path.rstrip("/")
    response.headers["Location"] = f"{base_path}/{asset.id}"
    return AssetResponse.model_validate(asset)


@router.get("", response_model=AssetPage, summary="List active production assets")
def list_assets(query: Annotated[AssetQuery, Query()], service: Service) -> AssetPage:
    """Exclude deleted assets; combine filters with AND and break sort ties by UUID."""
    return service.list(query)


@router.get(
    "/search",
    response_model=AssetPage,
    summary="Search, filter and sort active production assets",
)
def search_assets(query: Annotated[AssetQuery, Query()], service: Service) -> AssetPage:
    """Search name/description literally, with stable bounded pagination."""
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
    summary="Soft-delete an asset registration",
)
def delete_asset(asset_id: UUID, service: Service) -> Response:
    """Retain the row and source bytes; subsequent reads/updates/deletes return 404."""
    service.delete(asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def register_assets_api(application: FastAPI) -> None:
    """Install this slice's routes and explicit, secret-free error contracts."""
    application.include_router(router, prefix="/api/v1/assets")
    # Existing clients share the same lifecycle rules, including soft deletion.
    application.include_router(router, prefix="/assets", deprecated=True)

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
                code="asset_deleted" if error.deleted else "duplicate_asset",
                message=(
                    "A deleted asset retains this checksum; registration is reserved."
                    if error.deleted
                    else "An asset with this checksum exists; reuse the existing asset."
                ),
                existing_asset_id=error.existing_asset_id,
            )
        )
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))
