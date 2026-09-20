"""Coordinate dependency probes without exposing connection details."""

import logging

from app.api.health.schemas import DependencyChecks, ReadinessResponse
from app.core.config import Settings
from app.db.connectivity import postgres_ready, redis_ready

logger = logging.getLogger("wwml.health")


def check_readiness(settings: Settings) -> ReadinessResponse:
    """Probe both dependencies; return a stable, secret-free result."""
    checks = DependencyChecks(
        postgres=postgres_ready(settings), redis=redis_ready(settings)
    )
    if not checks.postgres:
        logger.warning("PostgreSQL readiness check failed")
    if not checks.redis:
        logger.warning("Redis readiness check failed")
    return ReadinessResponse(
        status="ok" if checks.postgres and checks.redis else "unavailable",
        checks=checks,
    )
