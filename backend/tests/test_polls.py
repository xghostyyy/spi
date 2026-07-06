"""Тесты опросов: создание, голосование (single/multi), закрытие, права."""

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


async def test_create_poll_and_vote(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "poll-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "poll-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "pollbob"}, headers=bob_headers)

    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "pollbob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    poll_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "poll": {"question": "Favorite color?", "options": ["Red", "Green", "Blue"]},
        },
        headers=alice_headers,
    )
    assert poll_resp.status_code == 201
    body = poll_resp.json()
    assert body["type"] == "poll"
    assert body["poll"]["question"] == "Favorite color?"
    assert len(body["poll"]["options"]) == 3
    assert body["poll"]["total_votes"] == 0
    message_public_id = body["message_public_id"]

    vote_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/poll/vote",
        json={"option_positions": [1]},
        headers=bob_headers,
    )
    assert vote_resp.status_code == 200
    poll = vote_resp.json()["poll"]
    assert poll["total_votes"] == 1
    assert poll["options"][1]["votes"] == 1
    assert poll["options"][1]["voted_by_me"] is True

    # revote changes the previous choice rather than adding to it
    revote_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/poll/vote",
        json={"option_positions": [2]},
        headers=bob_headers,
    )
    poll2 = revote_resp.json()["poll"]
    assert poll2["total_votes"] == 1
    assert poll2["options"][1]["votes"] == 0
    assert poll2["options"][2]["votes"] == 1


async def test_single_choice_poll_rejects_multiple_positions(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "poll2-alice@example.com", "111111")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Poll Group"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    poll_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "poll": {"question": "Pick one", "options": ["A", "B"], "multi_choice": False},
        },
        headers=alice_headers,
    )
    message_public_id = poll_resp.json()["message_public_id"]

    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/poll/vote",
        json={"option_positions": [0, 1]},
        headers=alice_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "single_choice_only"


async def test_multi_choice_poll_allows_multiple_positions(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "poll3-alice@example.com", "111111")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Poll Group 2"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    poll_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "poll": {"question": "Pick many", "options": ["A", "B", "C"], "multi_choice": True},
        },
        headers=alice_headers,
    )
    message_public_id = poll_resp.json()["message_public_id"]

    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/poll/vote",
        json={"option_positions": [0, 2]},
        headers=alice_headers,
    )
    assert resp.status_code == 200
    poll = resp.json()["poll"]
    assert poll["total_votes"] == 2
    assert poll["options"][0]["votes"] == 1
    assert poll["options"][2]["votes"] == 1


async def test_only_creator_can_close_poll(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "poll4-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "poll4-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "poll4bob"}, headers=bob_headers)

    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "poll4bob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    poll_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "poll": {"question": "Close me?", "options": ["Yes", "No"]},
        },
        headers=alice_headers,
    )
    message_public_id = poll_resp.json()["message_public_id"]

    forbidden = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/poll/close",
        headers=bob_headers,
    )
    assert forbidden.status_code == 403

    ok = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/poll/close",
        headers=alice_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["poll"]["closed_at"] is not None

    vote_after_close = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages/{message_public_id}/poll/vote",
        json={"option_positions": [0]},
        headers=bob_headers,
    )
    assert vote_after_close.status_code == 400
    assert vote_after_close.json()["code"] == "poll_closed"


async def test_forwarding_poll_message_rejected(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "poll5-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "poll5-bob@example.com", "222222")
    carol_token = await _login(client, monkeypatch, "poll5-carol@example.com", "333333")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    carol_headers = {"Authorization": f"Bearer {carol_token}"}
    await client.patch("/api/v1/users/me", json={"username": "poll5bob"}, headers=bob_headers)
    await client.patch("/api/v1/users/me", json={"username": "poll5carol"}, headers=carol_headers)

    chat_ab = (
        await client.post("/api/v1/chats", json={"username": "poll5bob"}, headers=alice_headers)
    ).json()["chat_public_id"]
    chat_ac = (
        await client.post("/api/v1/chats", json={"username": "poll5carol"}, headers=alice_headers)
    ).json()["chat_public_id"]

    poll_resp = await client.post(
        f"/api/v1/chats/{chat_ab}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "poll": {"question": "Forward me?", "options": ["Yes", "No"]},
        },
        headers=alice_headers,
    )
    message_public_id = poll_resp.json()["message_public_id"]

    forward_resp = await client.post(
        f"/api/v1/chats/{chat_ac}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "forward_from_message_public_id": message_public_id,
        },
        headers=alice_headers,
    )
    assert forward_resp.status_code == 400
    assert forward_resp.json()["code"] == "cannot_forward_poll"
