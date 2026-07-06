"""Тесты подписки на Web Push (без реальной отправки — VAPID-ключи в тестах пустые)."""

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


async def test_subscribe_is_idempotent(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "push-alice@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}

    body = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
        "keys": {"p256dh": "fake-p256dh-key", "auth": "fake-auth-secret"},
    }

    first = await client.post("/api/v1/push/subscribe", json=body, headers=headers)
    assert first.status_code == 204

    second = await client.post("/api/v1/push/subscribe", json=body, headers=headers)
    assert second.status_code == 204


async def test_unsubscribe_removes_subscription(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "push-bob@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}

    endpoint = "https://fcm.googleapis.com/fcm/send/xyz789"
    await client.post(
        "/api/v1/push/subscribe",
        json={"endpoint": endpoint, "keys": {"p256dh": "k", "auth": "a"}},
        headers=headers,
    )

    resp = await client.post(
        "/api/v1/push/unsubscribe", json={"endpoint": endpoint}, headers=headers
    )
    assert resp.status_code == 204

    # повторный unsubscribe того же endpoint — не ошибка, просто нет-op
    resp2 = await client.post(
        "/api/v1/push/unsubscribe", json={"endpoint": endpoint}, headers=headers
    )
    assert resp2.status_code == 204


async def test_vapid_public_key_endpoint_is_public(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/push/vapid-public-key")
    assert resp.status_code == 200
    assert "public_key" in resp.json()


async def test_sending_message_does_not_fail_without_vapid_keys(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VAPID-ключи в тестовом окружении не настроены — notify_chat_members должен
    молча ничего не делать, а не ронять отправку сообщения."""
    import uuid

    alice_token = await _login(client, monkeypatch, "push-carol@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "push-dave@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "pushdave"}, headers=bob_headers)

    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "pushdave"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    await client.post(
        "/api/v1/push/subscribe",
        json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/dave-device",
            "keys": {"p256dh": "k", "auth": "a"},
        },
        headers=bob_headers,
    )

    send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "hello"},
        headers=alice_headers,
    )
    assert send_resp.status_code == 201
