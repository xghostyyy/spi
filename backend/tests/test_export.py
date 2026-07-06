"""Тесты экспорта истории чата (JSON/HTML)."""

from __future__ import annotations

import json
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


async def test_export_json(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    alice_token = await _login(client, monkeypatch, "export-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "export-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "exportbob"}, headers=bob_headers)

    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "exportbob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "hello export"},
        headers=alice_headers,
    )

    resp = await client.get(
        f"/api/v1/chats/{chat_public_id}/export", params={"format": "json"}, headers=alice_headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert "attachment" in resp.headers["content-disposition"]

    data = json.loads(resp.content)
    assert data["chat"]["public_id"] == chat_public_id
    assert len(data["messages"]) == 1
    assert data["messages"][0]["body"] == "hello export"


async def test_export_html(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    alice_token = await _login(client, monkeypatch, "export2-alice@example.com", "111111")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Export Group"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "hello html export"},
        headers=alice_headers,
    )

    resp = await client.get(
        f"/api/v1/chats/{chat_public_id}/export", params={"format": "html"}, headers=alice_headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "hello html export" in resp.text
    assert "Export Group" in resp.text


async def test_export_requires_membership(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "export3-alice@example.com", "111111")
    carol_token = await _login(client, monkeypatch, "export3-carol@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    carol_headers = {"Authorization": f"Bearer {carol_token}"}

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Private Export Group"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    resp = await client.get(f"/api/v1/chats/{chat_public_id}/export", headers=carol_headers)
    assert resp.status_code == 404
