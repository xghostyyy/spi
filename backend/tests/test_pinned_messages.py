"""Тесты закреплённых сообщений в группах (пин/анпин, права, список)."""

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


async def test_owner_can_pin_and_unpin_message(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "pin-owner@example.com", "111111")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Pin Test"}, headers=owner_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    message_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "hello group"},
        headers=owner_headers,
    )
    message_public_id = message_resp.json()["message_public_id"]

    pin_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/pin",
        headers=owner_headers,
    )
    assert pin_resp.status_code == 204

    pinned = await client.get(f"/api/v1/chats/{chat_public_id}/pinned", headers=owner_headers)
    assert pinned.status_code == 200
    assert len(pinned.json()) == 1
    assert pinned.json()[0]["message_public_id"] == message_public_id

    unpin_resp = await client.delete(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/pin",
        headers=owner_headers,
    )
    assert unpin_resp.status_code == 204

    pinned_after = await client.get(f"/api/v1/chats/{chat_public_id}/pinned", headers=owner_headers)
    assert pinned_after.json() == []


async def test_pinning_produces_system_message(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "pin2-owner@example.com", "111111")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Pin System Msg"}, headers=owner_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    message_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "pin me"},
        headers=owner_headers,
    )
    message_public_id = message_resp.json()["message_public_id"]

    await client.post(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/pin",
        headers=owner_headers,
    )

    history = await client.get(f"/api/v1/chats/{chat_public_id}/messages", headers=owner_headers)
    events = [
        m["payload"]["event"] for m in history.json() if m["type"] == "system" and m["payload"]
    ]
    assert "message_pinned" in events


async def test_member_without_can_pin_cannot_pin(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "pin3-owner@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "pin3-bob@example.com", "222222")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch("/api/v1/users/me", json={"username": "pin3bob"}, headers=bob_headers)
    chat_resp = await client.post(
        "/api/v1/chats/group",
        json={"title": "Pin Perm Test", "member_usernames": ["pin3bob"]},
        headers=owner_headers,
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    message_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "not pinnable by bob"},
        headers=owner_headers,
    )
    message_public_id = message_resp.json()["message_public_id"]

    forbidden = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/pin",
        headers=bob_headers,
    )
    assert forbidden.status_code == 403


async def test_pinning_direct_chat_message_rejected(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "pin4-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "pin4-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "pin4bob"}, headers=bob_headers)

    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "pin4bob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    message_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "direct chat message"},
        headers=alice_headers,
    )
    message_public_id = message_resp.json()["message_public_id"]

    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/pin",
        headers=alice_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "not_a_group"
