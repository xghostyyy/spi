"""Точка входа FastAPI-приложения SPI Messenger."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import auth, blocks, bookmarks, chats, contacts, files, messages, sync, users
from app.core.config import get_settings
from app.core.limiter import limiter
from app.ws.router import router as ws_router

APP_VERSION = "0.1.0"
API_PREFIX = "/api/v1"


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    if isinstance(exc.detail, dict):
        content = exc.detail
    else:
        content = {"code": "error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


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

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    app.include_router(contacts.router, prefix=API_PREFIX)
    app.include_router(blocks.router, prefix=API_PREFIX)
    app.include_router(chats.router, prefix=API_PREFIX)
    app.include_router(messages.router, prefix=API_PREFIX)
    app.include_router(files.router, prefix=API_PREFIX)
    app.include_router(bookmarks.router, prefix=API_PREFIX)
    app.include_router(sync.router, prefix=API_PREFIX)
    app.include_router(ws_router)

    if settings.storage_backend == "local":
        media_root = Path(settings.storage_local_path)
        media_root.mkdir(parents=True, exist_ok=True)
        app.mount("/media", StaticFiles(directory=media_root), name="media")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": APP_VERSION, "env": settings.app_env}

    return app


app = create_app()
