"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.api.routes import chat, inspection, prediction

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI app
    """
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan events."""
        # Startup
        logger.info("FastAPI application starting...")
        yield
        # Shutdown
        logger.info("FastAPI application shutting down...")

    app = FastAPI(
        title="AIOPS API",
        description="Intelligent Operations Agent REST API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    app.include_router(inspection.router, prefix="/api/v1", tags=["inspection"])
    app.include_router(prediction.router, prefix="/api/v1", tags=["prediction"])

    # Health check
    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


# Global app instance
_app: Optional[FastAPI] = None


def get_app() -> FastAPI:
    """Get global FastAPI app instance."""
    global _app
    if _app is None:
        _app = create_app()
    return _app