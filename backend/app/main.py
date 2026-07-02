"""Точка входа FastAPI-приложения SPI Messenger."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

APP_VERSION = "0.1.0"


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="SPI Messenger API",
        version=APP_VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": APP_VERSION, "env": settings.app_env}

    return app


app = create_app()
