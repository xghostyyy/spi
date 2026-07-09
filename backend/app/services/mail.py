"""Отправка e-mail. Приоритет — HTTP API smtp.bz (порт 443), fallback — сырой SMTP
(aiosmtplib), в dev без того и другого код входа пишется в лог. См. ADR-024:
многие VPS-провайдеры по умолчанию блокируют исходящий SMTP (587/465), но не HTTPS."""

from __future__ import annotations

import asyncio
import logging
from email.message import EmailMessage

import aiosmtplib
import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("spi.mail")

_SMTP_BZ_API_URL = "https://api.smtp.bz/v1/smtp/send"
_SEND_TIMEOUT_SECONDS = 10.0
_LOGIN_CODE_SUBJECT = "Код входа в SPI Messenger"


async def send_login_code(email: str, code: str) -> None:
    settings = get_settings()
    body_text = f"Ваш код входа: {code}\nКод действителен 10 минут."

    if settings.smtp_api_key:
        await _send_via_api(settings, email, body_text)
        return

    if settings.smtp_host:
        await _send_via_smtp(settings, email, body_text)
        return

    logger.info("[DEV] Login code for %s: %s", email, code)


async def _send_via_api(settings: Settings, to: str, body_text: str) -> None:
    html_body = f"<html><body><p>{body_text.replace(chr(10), '<br>')}</p></body></html>"
    try:
        async with httpx.AsyncClient(timeout=_SEND_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                _SMTP_BZ_API_URL,
                headers={"Authorization": settings.smtp_api_key},
                json={
                    "from": settings.mail_from,
                    "to": to,
                    "subject": _LOGIN_CODE_SUBJECT,
                    "html": html_body,
                    "text": body_text,
                },
            )
            resp.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Не удалось отправить письмо с кодом входа на %s через API", to)
        raise


async def _send_via_smtp(settings: Settings, to: str, body_text: str) -> None:
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = _LOGIN_CODE_SUBJECT
    message.set_content(body_text)

    try:
        async with asyncio.timeout(_SEND_TIMEOUT_SECONDS):
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                start_tls=True,
            )
    except (TimeoutError, aiosmtplib.SMTPException):
        logger.exception("Не удалось отправить письмо с кодом входа на %s через SMTP", to)
        raise
