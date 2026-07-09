"""Тесты аутентификации: код на e-mail, вход, refresh, права доступа."""

from __future__ import annotations

import httpx
import pytest


async def test_request_and_verify_code_issues_token(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.auth.generate_login_code", lambda: "123456")
    email = "user@example.com"

    resp = await client.post("/api/v1/auth/request-code", json={"email": email})
    assert resp.status_code == 204

    resp = await client.post("/api/v1/auth/verify-code", json={"email": email, "code": "123456"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == email
    assert "spi_refresh" in resp.cookies


async def test_request_code_returns_error_when_mail_send_fails(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SMTP-сбой (в т.ч. зависшее/недоступное соединение с таймаутом в mail.py)
    должен вернуть понятную ошибку, а не оставить запрос без ответа."""

    async def _boom(email: str, code: str) -> None:
        raise TimeoutError("smtp connection timed out")

    monkeypatch.setattr("app.api.auth.send_login_code", _boom)

    resp = await client.post("/api/v1/auth/request-code", json={"email": "mailfail@example.com"})
    assert resp.status_code == 502
    assert resp.json()["code"] == "mail_send_failed"


async def test_verify_code_wrong_code_rejected(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.auth.generate_login_code", lambda: "111111")
    email = "user2@example.com"
    await client.post("/api/v1/auth/request-code", json={"email": email})

    resp = await client.post("/api/v1/auth/verify-code", json={"email": email, "code": "000000"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_code"


async def test_verify_code_without_request_rejected(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/verify-code", json={"email": "nobody@example.com", "code": "123456"}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_code"


async def test_me_requires_auth(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_refresh_rotates_cookie(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.auth.generate_login_code", lambda: "222222")
    email = "user3@example.com"
    await client.post("/api/v1/auth/request-code", json={"email": email})
    login_resp = await client.post(
        "/api/v1/auth/verify-code", json={"email": email, "code": "222222"}
    )
    assert login_resp.status_code == 200
    first_cookie = login_resp.cookies["spi_refresh"]

    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["access_token"]
    assert refresh_resp.cookies["spi_refresh"] != first_cookie


async def test_refresh_without_cookie_rejected(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
