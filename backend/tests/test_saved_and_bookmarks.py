"""Тесты Saved Messages и закладок на сообщения."""

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


async def test_saved_chat_is_idempotent_and_private(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "saved1@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}

    resp1 = await client.get("/api/v1/chats/saved", headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["type"] == "saved"

    resp2 = await client.get("/api/v1/chats/saved", headers=headers)
    assert resp2.json()["chat_public_id"] == resp1.json()["chat_public_id"]

    chat_public_id = resp1.json()["chat_public_id"]
    send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "note to self"},
        headers=headers,
    )
    assert send_resp.status_code == 201

    other_token = await _login(client, monkeypatch, "saved2@example.com", "222222")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    other_resp = await client.get(f"/api/v1/chats/{chat_public_id}/messages", headers=other_headers)
    assert other_resp.status_code == 404


async def test_bookmark_toggle(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    alice_token = await _login(client, monkeypatch, "bm-alice@example.com", "333333")
    bob_token = await _login(client, monkeypatch, "bm-bob@example.com", "444444")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch("/api/v1/users/me", json={"username": "bmbob"}, headers=bob_headers)
    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "bmbob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "hi"},
        headers=alice_headers,
    )
    message_public_id = send_resp.json()["message_public_id"]
    assert send_resp.json()["bookmarked"] is False

    toggle1 = await client.post(f"/api/v1/bookmarks/{message_public_id}", headers=bob_headers)
    assert toggle1.status_code == 200
    assert toggle1.json() == {"bookmarked": True}

    list_resp = await client.get("/api/v1/bookmarks", headers=bob_headers)
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["message_public_id"] == message_public_id

    alice_list = await client.get("/api/v1/bookmarks", headers=alice_headers)
    assert alice_list.json() == []

    toggle2 = await client.post(f"/api/v1/bookmarks/{message_public_id}", headers=bob_headers)
    assert toggle2.json() == {"bookmarked": False}

    list_resp2 = await client.get("/api/v1/bookmarks", headers=bob_headers)
    assert list_resp2.json() == []
