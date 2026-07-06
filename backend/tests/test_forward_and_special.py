"""Тесты пересылки сообщений и vCard/геолокации."""

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


async def test_forward_message_to_another_chat(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "fwd-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "fwd-bob@example.com", "222222")
    carol_token = await _login(client, monkeypatch, "fwd-carol@example.com", "333333")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    carol_headers = {"Authorization": f"Bearer {carol_token}"}

    await client.patch("/api/v1/users/me", json={"username": "fwdbob"}, headers=bob_headers)
    await client.patch("/api/v1/users/me", json={"username": "fwdcarol"}, headers=carol_headers)

    chat_ab = (
        await client.post("/api/v1/chats", json={"username": "fwdbob"}, headers=alice_headers)
    ).json()["chat_public_id"]
    chat_ac = (
        await client.post("/api/v1/chats", json={"username": "fwdcarol"}, headers=alice_headers)
    ).json()["chat_public_id"]

    original = await client.post(
        f"/api/v1/chats/{chat_ab}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "original text"},
        headers=alice_headers,
    )
    original_public_id = original.json()["message_public_id"]

    forwarded = await client.post(
        f"/api/v1/chats/{chat_ac}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "forward_from_message_public_id": original_public_id,
        },
        headers=alice_headers,
    )
    assert forwarded.status_code == 201
    forwarded_body = forwarded.json()
    assert forwarded_body["body"] == "original text"
    assert forwarded_body["forwarded_from_user_public_id"] is not None

    # чужое сообщение (не из своего чата) переслать нельзя
    forbidden = await client.post(
        f"/api/v1/chats/{chat_ac}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "forward_from_message_public_id": original_public_id,
        },
        headers=carol_headers,
    )
    assert forbidden.status_code == 404


async def test_send_contact_and_location_messages(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "special-alice@example.com", "444444")
    bob_token = await _login(client, monkeypatch, "special-bob@example.com", "555555")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "specialbob"}, headers=bob_headers)

    chat_public_id = (
        await client.post("/api/v1/chats", json={"username": "specialbob"}, headers=alice_headers)
    ).json()["chat_public_id"]

    contact_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "contact": {"name": "Ivan Petrov", "phone": "+79990000000"},
        },
        headers=alice_headers,
    )
    assert contact_resp.status_code == 201
    assert contact_resp.json()["type"] == "contact"
    assert contact_resp.json()["payload"] == {"name": "Ivan Petrov", "phone": "+79990000000"}

    location_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "location": {"lat": 55.75, "lng": 37.62}},
        headers=alice_headers,
    )
    assert location_resp.status_code == 201
    assert location_resp.json()["type"] == "location"
    assert location_resp.json()["payload"] == {"lat": 55.75, "lng": 37.62}
