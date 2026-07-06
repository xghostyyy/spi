"""Тесты стикеров и GIF-сообщений (Фаза 6)."""

from __future__ import annotations

import uuid

import httpx
import pytest


async def _login(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, email: str, code: str
) -> str:
    monkeypatch.setattr("app.api.auth.generate_login_code", lambda: code)
    await client.post("/api/v1/auth/request-code", json={"email": email})
    resp = await client.post("/api/v1/auth/verify-code", json={"email": email, "code": code})
    token: str = resp.json()["access_token"]
    return token


async def test_send_sticker_message(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "sticker-alice@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}
    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Stickers"}, headers=headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "sticker": {
                "pack": "cats",
                "sticker_id": "wave",
                "emoji": "\U0001f44b",
                "url": "/stickers/cats/wave.svg",
            },
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "sticker"
    assert body["payload"]["sticker_id"] == "wave"
    assert body["body"] is None


async def test_send_gif_message(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = await _login(client, monkeypatch, "gif-alice@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}
    chat_resp = await client.post("/api/v1/chats/group", json={"title": "Gifs"}, headers=headers)
    chat_public_id = chat_resp.json()["chat_public_id"]

    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "gif": {
                "url": "https://example.com/cat.gif",
                "preview_url": "https://example.com/cat-preview.gif",
                "width": 320,
                "height": 240,
            },
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "gif"
    assert body["payload"]["url"] == "https://example.com/cat.gif"


async def test_gifs_disabled_without_api_key(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "gif-bob@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}

    enabled_resp = await client.get("/api/v1/gifs/enabled", headers=headers)
    assert enabled_resp.status_code == 200
    assert enabled_resp.json() == {"enabled": False}

    search_resp = await client.get("/api/v1/gifs/search?q=cat", headers=headers)
    assert search_resp.status_code == 200
    assert search_resp.json() == []
