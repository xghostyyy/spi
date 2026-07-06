"""Тесты папок чатов (Фаза 6)."""

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


async def test_create_list_folder(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "folders-alice@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}

    chat_resp = await client.post("/api/v1/chats/group", json={"title": "Work"}, headers=headers)
    chat_public_id = chat_resp.json()["chat_public_id"]

    create_resp = await client.post(
        "/api/v1/folders",
        json={"name": "Работа", "chat_public_ids": [chat_public_id]},
        headers=headers,
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["name"] == "Работа"
    assert body["chat_public_ids"] == [chat_public_id]
    assert body["position"] == 1

    list_resp = await client.get("/api/v1/folders", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["folder_public_id"] == body["folder_public_id"]


async def test_create_folder_rejects_empty_name(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "folders-bob@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/folders", json={"name": "   ", "chat_public_ids": []}, headers=headers
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "name_required"


async def test_create_folder_rejects_foreign_chat(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "folders2-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "folders2-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Alice's group"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    resp = await client.post(
        "/api/v1/folders",
        json={"name": "Not mine", "chat_public_ids": [chat_public_id]},
        headers=bob_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "chat_not_found"


async def test_update_and_delete_folder(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "folders-carol@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}

    chat_a = (
        await client.post("/api/v1/chats/group", json={"title": "A"}, headers=headers)
    ).json()["chat_public_id"]
    chat_b = (
        await client.post("/api/v1/chats/group", json={"title": "B"}, headers=headers)
    ).json()["chat_public_id"]

    create_resp = await client.post(
        "/api/v1/folders", json={"name": "Draft", "chat_public_ids": [chat_a]}, headers=headers
    )
    folder_public_id = create_resp.json()["folder_public_id"]

    patch_resp = await client.patch(
        f"/api/v1/folders/{folder_public_id}",
        json={"name": "Renamed", "chat_public_ids": [chat_a, chat_b]},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Renamed"
    assert set(patch_resp.json()["chat_public_ids"]) == {chat_a, chat_b}

    delete_resp = await client.delete(f"/api/v1/folders/{folder_public_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/v1/folders", headers=headers)
    assert list_resp.json() == []


async def test_folder_not_found_for_other_user(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "folders3-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "folders3-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    create_resp = await client.post(
        "/api/v1/folders", json={"name": "Alice only"}, headers=alice_headers
    )
    folder_public_id = create_resp.json()["folder_public_id"]

    resp = await client.patch(
        f"/api/v1/folders/{folder_public_id}", json={"name": "Hijack"}, headers=bob_headers
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "folder_not_found"
