"""Тесты секретных (E2EE) чатов (Фаза 6, ADR-021)."""

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


async def _set_e2ee_key(client: httpx.AsyncClient, headers: dict[str, str], key: str) -> None:
    resp = await client.post("/api/v1/users/me/e2ee-key", json={"public_key": key}, headers=headers)
    assert resp.status_code == 200


async def test_create_secret_chat_requires_both_keys(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "secret-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "secret-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "secretbob"}, headers=bob_headers)

    no_key_resp = await client.post(
        "/api/v1/chats/secret", json={"username": "secretbob"}, headers=alice_headers
    )
    assert no_key_resp.status_code == 400
    assert no_key_resp.json()["code"] == "no_e2ee_key"

    await _set_e2ee_key(client, alice_headers, "alice-pubkey-base64")

    no_peer_key_resp = await client.post(
        "/api/v1/chats/secret", json={"username": "secretbob"}, headers=alice_headers
    )
    assert no_peer_key_resp.status_code == 400
    assert no_peer_key_resp.json()["code"] == "peer_no_e2ee_key"

    await _set_e2ee_key(client, bob_headers, "bob-pubkey-base64")

    ok_resp = await client.post(
        "/api/v1/chats/secret", json={"username": "secretbob"}, headers=alice_headers
    )
    assert ok_resp.status_code == 201
    body = ok_resp.json()
    assert body["is_secret"] is True
    assert body["peer_e2ee_public_key"] == "bob-pubkey-base64"


async def test_secret_chat_is_separate_from_regular_direct_chat(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "secret2-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "secret2-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "secret2bob"}, headers=bob_headers)
    await _set_e2ee_key(client, alice_headers, "alice-pubkey")
    await _set_e2ee_key(client, bob_headers, "bob-pubkey")

    regular_resp = await client.post(
        "/api/v1/chats", json={"username": "secret2bob"}, headers=alice_headers
    )
    secret_resp = await client.post(
        "/api/v1/chats/secret", json={"username": "secret2bob"}, headers=alice_headers
    )
    assert regular_resp.json()["chat_public_id"] != secret_resp.json()["chat_public_id"]
    assert regular_resp.json()["is_secret"] is False
    assert secret_resp.json()["is_secret"] is True


async def test_send_encrypted_message(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "secret3-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "secret3-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "secret3bob"}, headers=bob_headers)
    await _set_e2ee_key(client, alice_headers, "alice-pubkey")
    await _set_e2ee_key(client, bob_headers, "bob-pubkey")

    chat_resp = await client.post(
        "/api/v1/chats/secret", json={"username": "secret3bob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "encrypted": {"ciphertext": "cGxhaW50ZXh0", "iv": "aXY="},
        },
        headers=alice_headers,
    )
    assert send_resp.status_code == 201
    body = send_resp.json()
    assert body["type"] == "text"
    assert body["body"] is None
    assert body["payload"] == {"ciphertext": "cGxhaW50ZXh0", "iv": "aXY="}


async def test_secret_chat_rejects_plaintext_and_other_types(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "secret4-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "secret4-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "secret4bob"}, headers=bob_headers)
    await _set_e2ee_key(client, alice_headers, "alice-pubkey")
    await _set_e2ee_key(client, bob_headers, "bob-pubkey")

    chat_resp = await client.post(
        "/api/v1/chats/secret", json={"username": "secret4bob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    plaintext_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "plaintext leak"},
        headers=alice_headers,
    )
    assert plaintext_resp.status_code == 400
    assert plaintext_resp.json()["code"] == "secret_chat_text_only"

    mixed_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "encrypted": {"ciphertext": "abc", "iv": "def"},
            "location": {"lat": 1.0, "lng": 2.0},
        },
        headers=alice_headers,
    )
    assert mixed_resp.status_code == 400
    assert mixed_resp.json()["code"] == "secret_chat_text_only"


async def test_encrypted_field_rejected_in_regular_chat(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "secret5-alice@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}
    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Not secret"}, headers=headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "encrypted": {"ciphertext": "abc", "iv": "def"},
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "encrypted_not_allowed"


async def test_secret_chat_message_cannot_be_edited(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "secret6-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "secret6-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "secret6bob"}, headers=bob_headers)
    await _set_e2ee_key(client, alice_headers, "alice-pubkey")
    await _set_e2ee_key(client, bob_headers, "bob-pubkey")

    chat_resp = await client.post(
        "/api/v1/chats/secret", json={"username": "secret6bob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "encrypted": {"ciphertext": "abc", "iv": "def"},
        },
        headers=alice_headers,
    )
    message_public_id = send_resp.json()["message_public_id"]

    edit_resp = await client.patch(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}",
        json={"body": "trying to edit"},
        headers=alice_headers,
    )
    assert edit_resp.status_code == 400
    assert edit_resp.json()["code"] == "secret_chat_no_edit"


async def test_search_excludes_secret_chats(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "secret7-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "secret7-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch(
        "/api/v1/users/me",
        json={"username": "secret7bob", "display_name": "UniqueSecretBobName"},
        headers=bob_headers,
    )
    await _set_e2ee_key(client, alice_headers, "alice-pubkey")
    await _set_e2ee_key(client, bob_headers, "bob-pubkey")

    await client.post(
        "/api/v1/chats/secret", json={"username": "secret7bob"}, headers=alice_headers
    )

    search_resp = await client.get("/api/v1/search?q=UniqueSecretBobName", headers=alice_headers)
    assert search_resp.status_code == 200
    assert search_resp.json()["chats"] == []
