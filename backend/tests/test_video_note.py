"""Тест видеокружка (ADR-026): флаг is_video_note → тип сообщения video_note."""

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


async def test_video_note_flag_sets_message_type(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "vn-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "vn-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch("/api/v1/users/me", json={"username": "bobvn"}, headers=bob_headers)
    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "bobvn"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    upload_resp = await client.post(
        "/api/v1/files",
        files={"file": ("circle.webm", b"\x1a\x45\xdf\xa3fake-webm", "video/webm")},
        data={"kind": "video"},
        headers=alice_headers,
    )
    assert upload_resp.status_code == 201
    file_public_id = upload_resp.json()["public_id"]

    send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "file_public_ids": [file_public_id],
            "is_video_note": True,
        },
        headers=alice_headers,
    )
    assert send_resp.status_code == 201
    assert send_resp.json()["type"] == "video_note"


async def test_video_without_flag_stays_plain_video(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "vn2-alice@example.com", "333333")
    bob_token = await _login(client, monkeypatch, "vn2-bob@example.com", "444444")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch("/api/v1/users/me", json={"username": "bobvn2"}, headers=bob_headers)
    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "bobvn2"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    upload_resp = await client.post(
        "/api/v1/files",
        files={"file": ("clip.webm", b"\x1a\x45\xdf\xa3fake-webm", "video/webm")},
        data={"kind": "video"},
        headers=alice_headers,
    )
    file_public_id = upload_resp.json()["public_id"]

    send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "file_public_ids": [file_public_id]},
        headers=alice_headers,
    )
    assert send_resp.json()["type"] == "video"
