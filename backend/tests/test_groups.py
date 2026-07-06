"""Тесты групповых чатов: создание, участники, права, системные сообщения."""

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


async def _setup_group(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, prefix: str
) -> tuple[dict[str, str], dict[str, str], dict[str, str], str]:
    owner_token = await _login(client, monkeypatch, f"{prefix}-owner@example.com", "111111")
    bob_token = await _login(client, monkeypatch, f"{prefix}-bob@example.com", "222222")
    carol_token = await _login(client, monkeypatch, f"{prefix}-carol@example.com", "333333")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    carol_headers = {"Authorization": f"Bearer {carol_token}"}

    await client.patch("/api/v1/users/me", json={"username": f"{prefix}bob"}, headers=bob_headers)
    await client.patch(
        "/api/v1/users/me", json={"username": f"{prefix}carol"}, headers=carol_headers
    )

    create_resp = await client.post(
        "/api/v1/chats/group",
        json={"title": "Test Group", "member_usernames": [f"{prefix}bob"]},
        headers=owner_headers,
    )
    assert create_resp.status_code == 201
    chat_public_id: str = create_resp.json()["chat_public_id"]
    return owner_headers, bob_headers, carol_headers, chat_public_id


async def test_create_group_sets_owner_and_members(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_headers, _bob_headers, _carol_headers, chat_public_id = await _setup_group(
        client, monkeypatch, "grpA"
    )

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "dup check"}, headers=owner_headers
    )
    assert chat_resp.status_code == 201
    body = chat_resp.json()
    assert body["type"] == "group"
    assert body["my_role"] == "owner"
    assert body["member_count"] == 1

    members = await client.get(f"/api/v1/chats/{chat_public_id}/members", headers=owner_headers)
    assert members.status_code == 200
    roles = {m["username"]: m["role"] for m in members.json()}
    assert roles["grpAbob"] == "member"


async def test_non_member_cannot_add_members(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _owner_headers, _bob_headers, carol_headers, chat_public_id = await _setup_group(
        client, monkeypatch, "grpB"
    )

    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/members",
        json={"usernames": ["grpBcarol"]},
        headers=carol_headers,
    )
    assert resp.status_code == 404  # not a member, chat not found for them


async def test_member_without_invite_permission_cannot_add(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _owner_headers, bob_headers, _carol_headers, chat_public_id = await _setup_group(
        client, monkeypatch, "grpC"
    )

    # bob is a plain member (role=member), has no admin rights regardless of flag defaults
    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/members",
        json={"usernames": ["grpCcarol"]},
        headers=bob_headers,
    )
    assert resp.status_code == 403


async def test_owner_can_promote_and_remove_member(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_headers, bob_headers, _carol_headers, chat_public_id = await _setup_group(
        client, monkeypatch, "grpD"
    )

    members = (
        await client.get(f"/api/v1/chats/{chat_public_id}/members", headers=owner_headers)
    ).json()
    bob_public_id = next(m["user_public_id"] for m in members if m["username"] == "grpDbob")

    promote = await client.patch(
        f"/api/v1/chats/{chat_public_id}/members/{bob_public_id}",
        json={"role": "admin", "can_invite": True},
        headers=owner_headers,
    )
    assert promote.status_code == 200
    assert promote.json()["role"] == "admin"

    add_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/members",
        json={"usernames": ["nonexistentuser123"]},
        headers=bob_headers,
    )
    assert add_resp.status_code == 201  # bob is now admin with can_invite

    remove = await client.delete(
        f"/api/v1/chats/{chat_public_id}/members/{bob_public_id}", headers=owner_headers
    )
    assert remove.status_code == 204

    members_after = (
        await client.get(f"/api/v1/chats/{chat_public_id}/members", headers=owner_headers)
    ).json()
    assert all(m["username"] != "grpDbob" for m in members_after)


async def test_owner_cannot_leave_group_with_other_members(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_headers, _bob_headers, _carol_headers, chat_public_id = await _setup_group(
        client, monkeypatch, "grpE"
    )
    owner_result = await client.get(
        f"/api/v1/chats/{chat_public_id}/members", headers=owner_headers
    )
    owner_public_id = next(m["user_public_id"] for m in owner_result.json() if m["role"] == "owner")

    leave = await client.delete(
        f"/api/v1/chats/{chat_public_id}/members/{owner_public_id}", headers=owner_headers
    )
    assert leave.status_code == 400
    assert leave.json()["code"] == "owner_must_transfer"


async def test_update_group_info_requires_permission(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_headers, bob_headers, _carol_headers, chat_public_id = await _setup_group(
        client, monkeypatch, "grpF"
    )

    forbidden = await client.patch(
        f"/api/v1/chats/{chat_public_id}/info",
        json={"description": "hacked"},
        headers=bob_headers,
    )
    assert forbidden.status_code == 403

    ok = await client.patch(
        f"/api/v1/chats/{chat_public_id}/info",
        json={"title": "Renamed Group", "description": "New description"},
        headers=owner_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["title"] == "Renamed Group"
    assert ok.json()["description"] == "New description"


async def test_group_creation_produces_system_messages(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_headers, _bob_headers, _carol_headers, chat_public_id = await _setup_group(
        client, monkeypatch, "grpG"
    )

    history = await client.get(f"/api/v1/chats/{chat_public_id}/messages", headers=owner_headers)
    assert history.status_code == 200
    types = [m["type"] for m in history.json()]
    assert "system" in types
