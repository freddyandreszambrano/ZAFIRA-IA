from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.domain.exceptions import DomainError
from app.interfaces.api.v1 import api_router
from app.interfaces.health import router as health_router
from app.interfaces.security.hmac_auth import load_allowed_clients
from app.interfaces.security.openapi import apply_hmac_security_to_openapi


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Stateless MVP: no database nor pooled clients to initialize yet.
    # Fail fast si HMAC_ALLOWED_CLIENTS falta o es inválida: sin esto el primer
    # request firmaría contra una config rota en vez de impedir el despliegue.
    load_allowed_clients(get_settings())
    yield


def _build_openapi_schema(app: FastAPI) -> dict[str, Any]:
    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    settings = get_settings()
    apply_hmac_security_to_openapi(schema, settings.api_v1_prefix)
    return schema


def create_app() -> FastAPI:
    settings = get_settings()

    tags_metadata = [
        {"name": "health", "description": "Liveness/readiness probe."},
        {"name": "avatar", "description": "Semi-realistic avatar generation from a user photo."},
        {"name": "tryon", "description": "Virtual try-on of garments over an avatar."},
    ]

    app = FastAPI(
        title=settings.app_name,
        version=settings.api_version,
        description=(
            "ZAFIRA-IA — internal AI microservice. "
            "ZAFIRA-CORE (Django/Celery) → ZAFIRA-IA → AI models + object storage."
        ),
        lifespan=lifespan,
        openapi_url="/openapi.json",
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_tags=tags_metadata,
    )

    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        app.openapi_schema = _build_openapi_schema(app)
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, tags=["health"])
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.message, "code": exc.code},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.get("/", tags=["root"], summary="Service metadata")
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "health": "/health",
            "docs": "/docs" if settings.api_docs_enabled else "disabled",
            "openapi": "/openapi.json",
        }

    return app


app = create_app()
