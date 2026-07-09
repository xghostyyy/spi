"""Тесты каналов (Фаза 6, ADR-022): владелец/админы пишут, подписчики — только читают."""

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


async def test_create_channel(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = await _login(client, monkeypatch, "chan-alice@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/chats/channel",
        json={"title": "News", "description": "Latest updates"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_channel"] is True
    assert body["type"] == "group"
    assert body["my_role"] == "owner"
    assert body["title"] == "News"


async def test_subscriber_cannot_post_but_owner_can(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "chan2-owner@example.com", "111111")
    sub_token = await _login(client, monkeypatch, "chan2-sub@example.com", "222222")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    sub_headers = {"Authorization": f"Bearer {sub_token}"}
    await client.patch("/api/v1/users/me", json={"username": "chan2sub"}, headers=sub_headers)

    create_resp = await client.post(
        "/api/v1/chats/channel", json={"title": "Broadcast"}, headers=owner_headers
    )
    chat_public_id = create_resp.json()["chat_public_id"]

    await client.post(
        f"/api/v1/chats/{chat_public_id}/members",
        json={"usernames": ["chan2sub"]},
        headers=owner_headers,
    )

    sub_send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "trying to post"},
        headers=sub_headers,
    )
    assert sub_send_resp.status_code == 403
    assert sub_send_resp.json()["code"] == "channel_read_only"

    owner_send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "official announcement"},
        headers=owner_headers,
    )
    assert owner_send_resp.status_code == 201


async def test_subscribers_hidden_from_regular_members(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "chan3-owner@example.com", "111111")
    sub1_token = await _login(client, monkeypatch, "chan3-sub1@example.com", "222222")
    sub2_token = await _login(client, monkeypatch, "chan3-sub2@example.com", "333333")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    sub1_headers = {"Authorization": f"Bearer {sub1_token}"}
    sub2_headers = {"Authorization": f"Bearer {sub2_token}"}
    await client.patch("/api/v1/users/me", json={"username": "chan3sub1"}, headers=sub1_headers)
    await client.patch("/api/v1/users/me", json={"username": "chan3sub2"}, headers=sub2_headers)

    create_resp = await client.post(
        "/api/v1/chats/channel", json={"title": "Updates"}, headers=owner_headers
    )
    chat_public_id = create_resp.json()["chat_public_id"]
    await client.post(
        f"/api/v1/chats/{chat_public_id}/members",
        json={"usernames": ["chan3sub1", "chan3sub2"]},
        headers=owner_headers,
    )

    owner_view = await client.get(f"/api/v1/chats/{chat_public_id}/members", headers=owner_headers)
    assert len(owner_view.json()) == 3

    subscriber_view = await client.get(
        f"/api/v1/chats/{chat_public_id}/members", headers=sub1_headers
    )
    assert len(subscriber_view.json()) == 1
    assert subscriber_view.json()[0]["role"] == "owner"
