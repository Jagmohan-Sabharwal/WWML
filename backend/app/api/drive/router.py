"""Folder discovery endpoint with injectable credentials and transport."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse

from app.api.drive.client import authenticated_client
from app.api.drive.errors import DriveErrorCode, DriveReadError
from app.api.drive.schemas import (
    DriveErrorDetail,
    DriveErrorResponse,
    FolderReadQuery,
    FolderReadResponse,
)
from app.api.drive.service import DriveFolderReader
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/integrations/google-drive", tags=["google-drive"])

ERRORS: dict[DriveErrorCode, tuple[int, str]] = {
    "not_configured": (
        503,
        "Configure GOOGLE_DRIVE_FOLDER_ID to enable folder discovery.",
    ),
    "credentials_unavailable": (
        503,
        "Google Drive credentials are unavailable or invalid.",
    ),
    "access_denied": (403, "The configured identity cannot read this Drive folder."),
    "folder_unavailable": (
        404,
        "A required folder is unavailable or has been removed.",
    ),
    "not_a_folder": (503, "The configured Drive item must be a folder."),
    "upstream_unavailable": (
        503,
        "Google Drive is temporarily unavailable; try again later.",
    ),
    "invalid_response": (502, "Google Drive returned invalid or incomplete metadata."),
    "scan_limit_exceeded": (
        413,
        "The folder scan exceeded its configured resource limits.",
    ),
    "scan_timeout": (504, "The folder scan timed out."),
}


def get_folder_reader(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[DriveFolderReader]:
    if not settings.google_drive_folder_id:
        raise DriveReadError("not_configured")
    with authenticated_client(settings.google_drive_request_timeout_seconds) as client:
        yield DriveFolderReader(client, settings)


@router.get(
    "/files",
    response_model=FolderReadResponse,
    summary="Read files from the configured Google Drive folder",
    responses={
        code: {"model": DriveErrorResponse, "description": description}
        for code, description in [
            (403, "Drive access denied"),
            (404, "Folder unavailable"),
            (413, "Scan limit exceeded"),
            (502, "Invalid upstream response"),
            (503, "Configuration, credentials or upstream unavailable"),
            (504, "Scan deadline exceeded"),
        ]
    },
)
def read_files(
    query: Annotated[FolderReadQuery, Query()],
    reader: Annotated[DriveFolderReader, Depends(get_folder_reader)],
) -> FolderReadResponse:
    """Return metadata only. Shortcuts are reported but never followed."""
    return reader.read(recursive=query.recursive)


def register_drive_api(application: FastAPI) -> None:
    application.include_router(router)

    @application.exception_handler(DriveReadError)
    async def drive_error(request: Request, error: DriveReadError) -> JSONResponse:
        code, message = ERRORS[error.code]
        body = DriveErrorResponse(
            detail=DriveErrorDetail(code=error.code, message=message)
        )
        headers = (
            {"Retry-After": "30"} if error.code == "upstream_unavailable" else None
        )
        return JSONResponse(
            status_code=code, content=body.model_dump(mode="json"), headers=headers
        )
