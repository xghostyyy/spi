"""Тесты пригласительных ссылок в группу (создание, лимиты, join по токену)."""

from __future__ import annotations

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


async def test_create_invite_and_join(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "inv-owner@example.com", "111111")
    dave_token = await _login(client, monkeypatch, "inv-dave@example.com", "222222")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    dave_headers = {"Authorization": f"Bearer {dave_token}"}

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Invite Group"}, headers=owner_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    invite_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/invites", json={}, headers=owner_headers
    )
    assert invite_resp.status_code == 201
    token = invite_resp.json()["token"]
    assert len(token) == 22

    preview = await client.get(f"/api/v1/invites/{token}")
    assert preview.status_code == 200
    assert preview.json()["chat_title"] == "Invite Group"
    assert preview.json()["valid"] is True

    join_resp = await client.post(f"/api/v1/invites/{token}/join", headers=dave_headers)
    assert join_resp.status_code == 200
    assert join_resp.json()["type"] == "group"
    assert join_resp.json()["my_role"] == "member"

    members = (
        await client.get(f"/api/v1/chats/{chat_public_id}/members", headers=owner_headers)
    ).json()
    assert len(members) == 2


async def test_invite_max_uses_enforced(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "inv2-owner@example.com", "111111")
    dave_token = await _login(client, monkeypatch, "inv2-dave@example.com", "222222")
    erin_token = await _login(client, monkeypatch, "inv2-erin@example.com", "333333")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    dave_headers = {"Authorization": f"Bearer {dave_token}"}
    erin_headers = {"Authorization": f"Bearer {erin_token}"}

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Limited Invite"}, headers=owner_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    invite_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/invites", json={"max_uses": 1}, headers=owner_headers
    )
    token = invite_resp.json()["token"]

    first_join = await client.post(f"/api/v1/invites/{token}/join", headers=dave_headers)
    assert first_join.status_code == 200

    second_join = await client.post(f"/api/v1/invites/{token}/join", headers=erin_headers)
    assert second_join.status_code == 410
    assert second_join.json()["code"] == "invite_expired"


async def test_revoked_invite_cannot_be_used(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "inv3-owner@example.com", "111111")
    dave_token = await _login(client, monkeypatch, "inv3-dave@example.com", "222222")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    dave_headers = {"Authorization": f"Bearer {dave_token}"}

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Revoke Test"}, headers=owner_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    invite_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/invites", json={}, headers=owner_headers
    )
    token = invite_resp.json()["token"]

    revoke = await client.delete(
        f"/api/v1/chats/{chat_public_id}/invites/{token}", headers=owner_headers
    )
    assert revoke.status_code == 204

    join_resp = await client.post(f"/api/v1/invites/{token}/join", headers=dave_headers)
    assert join_resp.status_code == 410


async def test_only_invite_permitted_member_can_create_invite(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "inv4-owner@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "inv4-bob@example.com", "222222")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch("/api/v1/users/me", json={"username": "inv4bob"}, headers=bob_headers)
    chat_resp = await client.post(
        "/api/v1/chats/group",
        json={"title": "Perm Test", "member_usernames": ["inv4bob"]},
        headers=owner_headers,
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    forbidden = await client.post(
        f"/api/v1/chats/{chat_public_id}/invites", json={}, headers=bob_headers
    )
    assert forbidden.status_code == 403


async def test_banned_member_cannot_rejoin_via_invite(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "inv5-owner@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "inv5-bob@example.com", "222222")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch("/api/v1/users/me", json={"username": "inv5bob"}, headers=bob_headers)
    chat_resp = await client.post(
        "/api/v1/chats/group",
        json={"title": "Ban Test", "member_usernames": ["inv5bob"]},
        headers=owner_headers,
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    members = (
        await client.get(f"/api/v1/chats/{chat_public_id}/members", headers=owner_headers)
    ).json()
    bob_public_id = next(m["user_public_id"] for m in members if m["username"] == "inv5bob")

    await client.delete(
        f"/api/v1/chats/{chat_public_id}/members/{bob_public_id}", headers=owner_headers
    )

    invite_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/invites", json={}, headers=owner_headers
    )
    token = invite_resp.json()["token"]

    rejoin = await client.post(f"/api/v1/invites/{token}/join", headers=bob_headers)
    assert rejoin.status_code == 403
    assert rejoin.json()["code"] == "banned_from_chat"
