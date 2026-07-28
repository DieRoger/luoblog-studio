"""FastAPI application factory.

Usage:
    uvicorn src.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from logging_config import configure as configure_logging
from api.middleware import RequestContextMiddleware
from api.router import api_router
from api.errors import register_exception_handlers
from infrastructure.persistence.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    configure_logging()
    # DB engine is created on first use; no explicit connect needed at startup
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="LuoBlog Studio API",
        description="Personal AI Engineering Knowledge OS",
        version="0.1.0",
        docs_url="/docs" if settings.app_debug else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request context (logging, timing)
    app.add_middleware(RequestContextMiddleware)

    # Routes
    app.include_router(api_router, prefix="/api/v1")

    # Error handlers
    register_exception_handlers(app)

    return app
