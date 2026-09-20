"""Health HTTP endpoints; liveness never depends on external services."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.health.schemas import HealthResponse, ReadinessResponse
from app.api.health.service import check_readiness
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report whether the API process can serve requests."""
    return HealthResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        503: {"model": ReadinessResponse, "description": "Dependency unavailable"}
    },
)
def readiness(
    response: Response, settings: Annotated[Settings, Depends(get_settings)]
) -> ReadinessResponse:
    """Check PostgreSQL and Redis connectivity for container readiness."""
    result = check_readiness(settings)
    if result.status == "unavailable":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
