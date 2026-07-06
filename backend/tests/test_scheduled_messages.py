"""Тесты отложенной отправки сообщений (Фаза 6)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.db.models import Message
from app.services.scheduler import deliver_due_scheduled_messages
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _login(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, email: str, code: str
) -> str:
    monkeypatch.setattr("app.api.auth.generate_login_code", lambda: code)
    await client.post("/api/v1/auth/request-code", json={"email": email})
    resp = await client.post("/api/v1/auth/verify-code", json={"email": email, "code": code})
    token: str = resp.json()["access_token"]
    return token


async def test_scheduled_message_rejects_past_time(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "sched-alice@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}
    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Sched Group"}, headers=headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "too late", "scheduled_at": past},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "scheduled_at_in_past"


async def test_scheduled_message_hidden_until_delivered(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    alice_token = await _login(client, monkeypatch, "sched2-alice@example.com", "111111")
    bob_token = await _login(client, monkeypatch, "sched2-bob@example.com", "222222")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    await client.patch("/api/v1/users/me", json={"username": "sched2bob"}, headers=bob_headers)

    chat_resp = await client.post(
        "/api/v1/chats", json={"username": "sched2bob"}, headers=alice_headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={
            "client_msg_id": str(uuid.uuid4()),
            "body": "surprise later",
            "scheduled_at": future,
        },
        headers=alice_headers,
    )
    assert send_resp.status_code == 201
    message_public_id = send_resp.json()["message_public_id"]
    assert send_resp.json()["scheduled_at"] is not None

    # не видно ни отправителю, ни получателю в обычной истории
    alice_history = await client.get(
        f"/api/v1/chats/{chat_public_id}/messages", headers=alice_headers
    )
    assert all(m["message_public_id"] != message_public_id for m in alice_history.json())
    bob_history = await client.get(f"/api/v1/chats/{chat_public_id}/messages", headers=bob_headers)
    assert all(m["message_public_id"] != message_public_id for m in bob_history.json())

    # видно в списке отложенных у отправителя
    scheduled_list = await client.get(
        f"/api/v1/chats/{chat_public_id}/messages/scheduled", headers=alice_headers
    )
    assert len(scheduled_list.json()) == 1
    assert scheduled_list.json()[0]["message_public_id"] == message_public_id

    # "наступает" время отправки
    result = await db_session.execute(select(Message).where(Message.public_id == message_public_id))
    message = result.scalar_one()
    message.scheduled_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    delivered_count = await deliver_due_scheduled_messages(db_session)
    assert delivered_count == 1

    bob_history_after = await client.get(
        f"/api/v1/chats/{chat_public_id}/messages", headers=bob_headers
    )
    bodies = [m["body"] for m in bob_history_after.json()]
    assert "surprise later" in bodies

    scheduled_list_after = await client.get(
        f"/api/v1/chats/{chat_public_id}/messages/scheduled", headers=alice_headers
    )
    assert scheduled_list_after.json() == []


async def test_reschedule_and_cancel(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "sched3-alice@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}
    chat_resp = await client.post(
        "/api/v1/chats/group", json={"title": "Sched Group 2"}, headers=headers
    )
    chat_public_id = chat_resp.json()["chat_public_id"]

    future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    send_resp = await client.post(
        f"/api/v1/chats/{chat_public_id}/messages",
        json={"client_msg_id": str(uuid.uuid4()), "body": "reschedule me", "scheduled_at": future},
        headers=headers,
    )
    message_public_id = send_resp.json()["message_public_id"]

    new_time = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
    reschedule_resp = await client.patch(
        f"/api/v1/chats/{chat_public_id}/messages/scheduled/{message_public_id}",
        json={"scheduled_at": new_time},
        headers=headers,
    )
    assert reschedule_resp.status_code == 200

    cancel_resp = await client.delete(
        f"/api/v1/chats/{chat_public_id}/messages/scheduled/{message_public_id}",
        headers=headers,
    )
    assert cancel_resp.status_code == 204

    scheduled_list = await client.get(
        f"/api/v1/chats/{chat_public_id}/messages/scheduled", headers=headers
    )
    assert scheduled_list.json() == []
