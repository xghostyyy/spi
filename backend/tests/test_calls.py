"""Тесты звонков (Фаза 6): лог-сообщение о звонке (REST).

Сигналинг WebRTC (app/ws/router.py::_handle_call_signal) — чистый relay поверх
/ws и в этом проекте не покрыт тестами так же, как typing/read/presence-хендлеры
того же модуля (нет инфраструктуры для WS-тестов, см. ADR-020).
"""

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


async def test_send_call_log_message(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "call-alice@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}
    chat_resp = await client.post("/api/v1/chats/group", json={"title": "Calls"}, headers=headers)
    chat_public_id = chat_resp.json()["chat_public_id"]

    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "call": {"kind": "audio", "outcome": "answered", "duration_seconds": 42},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["type"] == "call"
    assert body["payload"] == {"kind": "audio", "outcome": "answered", "duration_seconds": 42}
    assert body["body"] is None


async def test_call_log_rejects_invalid_outcome(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "call-bob@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}
    chat_resp = await client.post("/api/v1/chats/group", json={"title": "Calls"}, headers=headers)
    chat_public_id = chat_resp.json()["chat_public_id"]

    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "call": {"kind": "video", "outcome": "hung_up", "duration_seconds": 1},
        },
        headers=headers,
    )
    assert resp.status_code == 422
