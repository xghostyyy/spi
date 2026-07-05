"""Тесты поиска: по чатам (username/имя) и по тексту сообщений."""

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


async def test_global_search_finds_chat_and_message(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "search-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "search-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch(
        "/api/v1/users/me",
        json={"username": "searchbob", "display_name": "Bob Searchable"},
        headers=bob_headers,
    )
    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "searchbob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "уникальнаяфразадляпоиска"},
        headers=alice_headers,
    )

    chat_search = await client.get(
        "/api/v1/search", params={"q": "searchbob"}, headers=alice_headers
    )
    assert chat_search.status_code == 200
    assert len(chat_search.json()["chats"]) == 1
    assert chat_search.json()["chats"][0]["chat_public_id"] == chat_public_id

    message_search = await client.get(
        "/api/v1/search", params={"q": "уникальнаяфразадляпоиска"}, headers=alice_headers
    )
    assert len(message_search.json()["messages"]) == 1

    nobody_search = await client.get(
        "/api/v1/search", params={"q": "совершенно-не-найдётся-999"}, headers=alice_headers
    )
    assert nobody_search.json() == {"chats": [], "messages": []}


async def test_in_chat_search_filters_by_text(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "search2-alice@example.com", "333333")
    bob_token = await _login(client, monkeypatch, "search2-bob@example.com", "444444")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    await client.patch("/api/v1/users/me", json={"username": "search2bob"}, headers=bob_headers)
    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "search2bob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "яблоко"},
        headers=alice_headers,
    )
    await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "апельсин"},
        headers=alice_headers,
    )

    resp = await client.get(
        f"/api/v1/chats/{chat_public_id}/messages",
        params={"q": "яблоко"},
        headers=alice_headers,
    )
    assert resp.status_code == 200
    bodies = [m["body"] for m in resp.json()]
    assert bodies == ["яблоко"]
