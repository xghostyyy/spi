"""Тесты загрузки медиафайлов и вложений в сообщениях."""

from __future__ import annotations

import base64

import httpx
import pytest

# 1x1 прозрачный PNG
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


async def _login(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, email: str, code: str
) -> str:
    monkeypatch.setattr("app.api.auth.generate_login_code", lambda: code)
    await client.post("/api/v1/auth/request-code", json={"email": email})
    resp = await client.post("/api/v1/auth/verify-code", json={"email": email, "code": code})
    token: str = resp.json()["access_token"]
    return token


async def test_upload_image_and_send_photo_message(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "alice-media@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "bob-media@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch("/api/v1/users/me", json={"username": "bobmedia"}, headers=bob_headers)

    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "bobmedia"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    upload_resp = await client.post(
        "/api/v1/files",
        files={"file": ("pixel.png", _TINY_PNG, "image/png")},
        data={"kind": "image"},
        headers=alice_headers,
    )
    assert upload_resp.status_code == 201
    file_public_id = upload_resp.json()["public_id"]
    assert upload_resp.json()["thumb_url"] is not None

    send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": "11111111-1111-1111-1111-111111111111",
            "file_public_ids": [file_public_id],
        },
        headers=alice_headers,
    )
    assert send_resp.status_code == 201
    body = send_resp.json()
    assert body["type"] == "photo"
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["kind"] == "image"


async def test_send_message_without_body_or_files_rejected(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "solo-media@example.com", "333333")
    headers = {"Authorization": f"Bearer {token}"}
    other_token = await _login(client, monkeypatch, "peer-media@example.com", "444444")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    await client.patch("/api/v1/users/me", json={"username": "peermedia"}, headers=other_headers)

    chat_resp = await client.post("/api/v1/chats", json={"username": "peermedia"}, headers=headers)
    chat_public_id = chat_resp.json()["chat_public_id"]

    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": "22222222-2222-2222-2222-222222222222"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "empty_message"
