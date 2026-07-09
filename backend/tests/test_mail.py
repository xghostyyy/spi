"""Юнит-тесты выбора способа отправки в mail.py (ADR-024) — без БД, HTTP/SMTP замоканы."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest
from app.services import mail


@dataclass
class _FakeSettings:
    smtp_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "noreply@spi-2015.ru"


async def test_no_config_logs_code_instead_of_sending(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings())
    with caplog.at_level("INFO", logger="spi.mail"):
        await mail.send_login_code("user@example.com", "123456")
    assert "[DEV] Login code" in caplog.text


async def test_api_key_present_sends_via_http_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings(smtp_api_key="secret-key"))

    calls: list[dict[str, object]] = []

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> _FakeResponse:
            calls.append({"url": url, **kwargs})
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    await mail.send_login_code("user@example.com", "654321")

    assert len(calls) == 1
    assert calls[0]["url"] == mail._SMTP_BZ_API_URL
    assert calls[0]["headers"] == {"Authorization": "secret-key"}
    body = calls[0]["json"]
    assert isinstance(body, dict)
    assert body["to"] == "user@example.com"
    assert "654321" in body["text"]


async def test_api_send_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings(smtp_api_key="secret-key"))

    class _FailingAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FailingAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> None:
            raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(httpx, "AsyncClient", _FailingAsyncClient)

    with pytest.raises(httpx.HTTPError):
        await mail.send_login_code("user@example.com", "111111")


async def test_smtp_fallback_used_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mail, "get_settings", lambda: _FakeSettings(smtp_host="smtp.example.com"))

    calls: list[dict[str, object]] = []

    async def _fake_send(message: object, **kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(mail.aiosmtplib, "send", _fake_send)

    await mail.send_login_code("user@example.com", "222222")

    assert len(calls) == 1
    assert calls[0]["hostname"] == "smtp.example.com"
