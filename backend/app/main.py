"""ASGI entry point and application composition."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.assets.router import register_assets_api
from app.api.drive.router import register_drive_api
from app.api.health.router import router as health_router
from app.api.imports.router import router as imports_router
from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.session import create_database_engine, create_session_factory

logger = logging.getLogger("wwml")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an isolated application without opening external connections."""
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(config.log_level)
        engine = create_database_engine(config)
        application.state.session_factory = create_session_factory(engine)
        logger.info("WWML API started")
        try:
            yield
        finally:
            engine.dispose()
            logger.info("WWML API stopped")

    application = FastAPI(title=config.app_name, version="0.1.0", lifespan=lifespan)
    application.state.settings = config
    application.include_router(health_router)
    application.include_router(imports_router)
    register_assets_api(application)
    register_drive_api(application)
    return application


app = create_app()
