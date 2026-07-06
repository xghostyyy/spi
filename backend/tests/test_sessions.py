"""Тесты списка активных сессий и отзыва по ID (Active Sessions)."""

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


async def test_list_sessions_marks_current(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _login(client, monkeypatch, "session-alice@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/auth/sessions", headers=headers)
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 1
    assert sessions[0]["is_current"] is True
    assert sessions[0]["device_label"] is not None


async def test_revoke_session(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = await _login(client, monkeypatch, "session-bob@example.com", "111111")
    headers = {"Authorization": f"Bearer {token}"}

    sessions = (await client.get("/api/v1/auth/sessions", headers=headers)).json()
    session_id = sessions[0]["id"]

    revoke_resp = await client.delete(f"/api/v1/auth/sessions/{session_id}", headers=headers)
    assert revoke_resp.status_code == 204

    after = (await client.get("/api/v1/auth/sessions", headers=headers)).json()
    assert after == []


async def test_cannot_revoke_other_users_session(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice_token = await _login(client, monkeypatch, "session-carol@example.com", "111111")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    alice_sessions = (await client.get("/api/v1/auth/sessions", headers=alice_headers)).json()
    alice_session_id = alice_sessions[0]["id"]

    dave_token = await _login(client, monkeypatch, "session-dave@example.com", "222222")
    dave_headers = {"Authorization": f"Bearer {dave_token}"}

    resp = await client.delete(f"/api/v1/auth/sessions/{alice_session_id}", headers=dave_headers)
    assert resp.status_code == 404
