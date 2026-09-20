"""Public contracts for platform health probes."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"


class DependencyChecks(BaseModel):
    postgres: bool
    redis: bool


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: DependencyChecks
