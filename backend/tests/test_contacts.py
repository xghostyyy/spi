"""Тесты контактов: идемпотентность добавления (ON CONFLICT), права доступа."""

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


async def test_add_contact_is_idempotent(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "owner@example.com", "111111")
    target_token = await _login(client, monkeypatch, "target@example.com", "222222")

    resp = await client.patch(
        "/api/v1/users/me",
        json={"username": "targetuser"},
        headers={"Authorization": f"Bearer {target_token}"},
    )
    assert resp.status_code == 200

    headers = {"Authorization": f"Bearer {owner_token}"}
    resp1 = await client.post("/api/v1/contacts", json={"username": "targetuser"}, headers=headers)
    assert resp1.status_code == 201
    resp2 = await client.post("/api/v1/contacts", json={"username": "targetuser"}, headers=headers)
    assert resp2.status_code == 201

    list_resp = await client.get("/api/v1/contacts", headers=headers)
    assert list_resp.status_code == 200
    contacts = list_resp.json()
    assert len(contacts) == 1
    assert contacts[0]["username"] == "targetuser"


async def test_add_contact_unknown_username_404(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "solo@example.com", "333333")
    resp = await client.post(
        "/api/v1/contacts",
        json={"username": "doesnotexist"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_contacts_require_auth(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/contacts")
    assert resp.status_code == 401


async def test_blocked_user_cannot_be_added_as_contact(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_token = await _login(client, monkeypatch, "blocker@example.com", "444444")
    blockee_token = await _login(client, monkeypatch, "blockee@example.com", "555555")

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    blockee_headers = {"Authorization": f"Bearer {blockee_token}"}

    resp = await client.patch(
        "/api/v1/users/me", json={"username": "blockeeuser"}, headers=blockee_headers
    )
    assert resp.status_code == 200

    block_resp = await client.post(
        "/api/v1/blocks", json={"username": "blockeeuser"}, headers=owner_headers
    )
    assert block_resp.status_code == 204

    contact_resp = await client.post(
        "/api/v1/contacts", json={"username": "blockeeuser"}, headers=owner_headers
    )
    assert contact_resp.status_code == 403
    assert contact_resp.json()["code"] == "blocked"
