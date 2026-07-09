"""Тесты открытого каталога сотрудников (ADR-025)."""

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


async def test_directory_lists_others_without_email(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "dir-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "dir-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch(
        "/api/v1/users/me",
        json={"username": "bobdir", "display_name": "Bob Directory"},
        headers=bob_headers,
    )

    resp = await client.get("/api/v1/users/directory", headers=alice_headers)
    assert resp.status_code == 200
    users = resp.json()
    public_ids = {u["public_id"] for u in users}

    # Bob виден, себя (alice) в каталоге нет.
    bob = next(u for u in users if u["username"] == "bobdir")
    assert bob["display_name"] == "Bob Directory"
    assert "email" not in bob  # приватность: e-mail не отдаётся
    me = await client.get("/api/v1/users/me", headers=alice_headers)
    assert me.json()["public_id"] not in public_ids


async def test_directory_search_filters_by_name(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "dir2-alice@example.com", "333333")
    bob_token = await _login(client, monkeypatch, "dir2-bob@example.com", "444444")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch(
        "/api/v1/users/me",
        json={"username": "uniquebob2", "display_name": "Unique Bob Two"},
        headers=bob_headers,
    )

    hit = await client.get(
        "/api/v1/users/directory", params={"q": "uniquebob2"}, headers=alice_headers
    )
    assert [u["username"] for u in hit.json()] == ["uniquebob2"]

    miss = await client.get(
        "/api/v1/users/directory", params={"q": "нет-такого-999"}, headers=alice_headers
    )
    assert miss.json() == []


async def test_start_direct_chat_by_public_id(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Каталог отдаёт public_id — чат создаётся по нему (не обязательно по username)."""
    alice_token = await _login(client, monkeypatch, "dir3-alice@example.com", "555555")
    bob_token = await _login(client, monkeypatch, "dir3-bob@example.com", "666666")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    bob_me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {bob_token}"})
    bob_public_id = bob_me.json()["public_id"]

    chat_resp = await client.post(
        "/api/v1/chats", json={"peer_public_id": bob_public_id}, headers=alice_headers
    )
    assert chat_resp.status_code == 201
    assert chat_resp.json()["type"] == "direct"


async def test_create_direct_chat_without_target_rejected(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "dir4-alice@example.com", "777777")
    resp = await client.post("/api/v1/chats", json={}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "missing_target"
