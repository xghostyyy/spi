"""Поиск GIF через Tenor API (Фаза 6). Без TENOR_API_KEY — деградирует до пустой выдачи."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.db.models import User

router = APIRouter(prefix="/gifs", tags=["gifs"])

_TENOR_SEARCH_URL = "https://tenor.googleapis.com/v2/search"
_REQUEST_TIMEOUT_SECONDS = 5.0


class GifResult(BaseModel):
    id: str
    url: str
    preview_url: str
    width: int
    height: int


@router.get("/enabled")
async def gifs_enabled() -> dict[str, bool]:
    return {"enabled": bool(get_settings().tenor_api_key)}


@router.get("/search", response_model=list[GifResult])
@limiter.limit("30/minute")
async def search_gifs(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(default=20, le=50, ge=1),
    user: User = Depends(get_current_user),
) -> list[GifResult]:
    settings = get_settings()
    if not settings.tenor_api_key:
        return []

    params = {
        "q": q,
        "key": settings.tenor_api_key,
        "client_key": "spi-messenger",
        "limit": str(limit),
        "media_filter": "gif",
        "contentfilter": "medium",
    }
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.get(_TENOR_SEARCH_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPError:
            return []
        data = resp.json()

    results: list[GifResult] = []
    for item in data.get("results", []):
        media = item.get("media_formats", {}).get("gif")
        if not media:
            continue
        dims = media.get("dims") or [0, 0]
        results.append(
            GifResult(
                id=item["id"],
                url=media["url"],
                preview_url=(item.get("media_formats", {}).get("tinygif") or media)["url"],
                width=dims[0] if len(dims) > 0 else 0,
                height=dims[1] if len(dims) > 1 else 0,
            )
        )
    return results
