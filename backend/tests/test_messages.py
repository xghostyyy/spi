"""Тесты сообщений: идемпотентность отправки (client_msg_id), права доступа."""

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


async def _create_direct_chat(
    client: httpx.AsyncClient, headers: dict[str, str], username: str
) -> str:
    resp = await client.post("/api/v1/chats", json={"username": username}, headers=headers)
    assert resp.status_code == 201
    chat_public_id: str = resp.json()["chat_public_id"]
    return chat_public_id


async def test_send_message_is_idempotent(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch("/api/v1/users/me", json={"username": "bob"}, headers=bob_headers)

    chat_public_id = await _create_direct_chat(client, alice_headers, "bob")

    client_msg_id = str(uuid.uuid4())
    body = {"client_msg_id": client_msg_id, "body": "Привет!"}

    resp1 = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages", json=body, headers=alice_headers
    )
    assert resp1.status_code == 201
    message_public_id = resp1.json()["message_public_id"]

    resp2 = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages", json=body, headers=alice_headers
    )
    assert resp2.status_code == 201
    assert resp2.json()["message_public_id"] == message_public_id

    history = await client.get(f"/api/v1/chats/{chat_public_id}/messages", headers=alice_headers)
    assert history.status_code == 200
    assert len(history.json()) == 1


async def test_only_member_can_read_or_send(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "alice2@example.com", "333333")
    bob_token = await _login(client, monkeypatch, "bob2@example.com", "444444")
    eve_token = await _login(client, monkeypatch, "eve@example.com", "555555")

    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    eve_headers = {"Authorization": f"Bearer {eve_token}"}

    await client.patch("/api/v1/users/me", json={"username": "bob2"}, headers=bob_headers)
    chat_public_id = await _create_direct_chat(client, alice_headers, "bob2")

    resp = await client.get(f"/api/v1/chats/{chat_public_id}/messages", headers=eve_headers)
    assert resp.status_code == 404

    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "hi"},
        headers=eve_headers,
    )
    assert resp.status_code == 404


async def test_edit_and_delete_permissions(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "alice3@example.com", "666666")
    bob_token = await _login(client, monkeypatch, "bob3@example.com", "777777")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch("/api/v1/users/me", json={"username": "bob3"}, headers=bob_headers)
    chat_public_id = await _create_direct_chat(client, alice_headers, "bob3")

    send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "original"},
        headers=alice_headers,
    )
    message_public_id = send_resp.json()["message_public_id"]

    edit_by_bob = await client.patch(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}",
        json={"body": "hacked"},
        headers=bob_headers,
    )
    assert edit_by_bob.status_code == 403

    edit_by_alice = await client.patch(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}",
        json={"body": "edited"},
        headers=alice_headers,
    )
    assert edit_by_alice.status_code == 200
    assert edit_by_alice.json()["body"] == "edited"
    assert edit_by_alice.json()["edited_at"] is not None

    delete_all_by_bob = await client.delete(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}?scope=all",
        headers=bob_headers,
    )
    assert delete_all_by_bob.status_code == 403

    delete_self_by_bob = await client.delete(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}?scope=self",
        headers=bob_headers,
    )
    assert delete_self_by_bob.status_code == 204
