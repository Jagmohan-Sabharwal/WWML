"""ASGI entry point and application composition."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health.router import router as health_router
from app.core.config import Settings
from app.core.logging import configure_logging

logger = logging.getLogger("wwml")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an isolated application without opening external connections."""
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(config.log_level)
        logger.info("WWML API started")
        yield
        logger.info("WWML API stopped")

    application = FastAPI(title=config.app_name, version="0.1.0", lifespan=lifespan)
    application.state.settings = config
    application.include_router(health_router)
    return application


app = create_app()
