"""Тесты медиа-архива чата (вкладки Медиа/Файлы/Ссылки/Голосовые)."""

from __future__ import annotations

import io
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


async def test_media_archive_tabs(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "media-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "media-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "mediabob"}, headers=bob_headers)

    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "mediabob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    # обычный текст с ссылкой
    await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "check this out https://example.com"},
        headers=alice_headers,
    )
    # текст без ссылки — не должен попасть во вкладку "ссылки"
    await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "just plain text"},
        headers=alice_headers,
    )

    doc_upload = await client.post(
        "/api/v1/files",
        files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        data={"kind": "document"},
        headers=alice_headers,
    )
    assert doc_upload.status_code == 201
    doc_public_id = doc_upload.json()["public_id"]
    await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "file_public_ids": [doc_public_id]},
        headers=alice_headers,
    )

    links_resp = await client.get(
        f"/api/v1/chats/{chat_public_id}/media", params={"tab": "links"}, headers=alice_headers
    )
    assert links_resp.status_code == 200
    assert len(links_resp.json()) == 1
    assert "example.com" in links_resp.json()[0]["body"]

    files_resp = await client.get(
        f"/api/v1/chats/{chat_public_id}/media", params={"tab": "files"}, headers=alice_headers
    )
    assert files_resp.status_code == 200
    assert len(files_resp.json()) == 1
    assert files_resp.json()[0]["type"] == "document"

    media_resp = await client.get(
        f"/api/v1/chats/{chat_public_id}/media", params={"tab": "media"}, headers=alice_headers
    )
    assert media_resp.status_code == 200
    assert media_resp.json() == []

    voice_resp = await client.get(
        f"/api/v1/chats/{chat_public_id}/media", params={"tab": "voice"}, headers=alice_headers
    )
    assert voice_resp.status_code == 200
    assert voice_resp.json() == []


async def test_media_archive_requires_membership(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "media2-alice@example.com", "111111")
    carol_token = await _login(client, monkeypatch, "media2-carol@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    carol_headers = {"Authorization": f"Bearer {carol_token}"}

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Media Group"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    resp = await client.get(
        f"/api/v1/chats/{chat_public_id}/media", params={"tab": "media"}, headers=carol_headers
    )
    assert resp.status_code == 404
