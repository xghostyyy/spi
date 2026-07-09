"""Отправка e-mail. В dev (без SMTP) код входа пишется в лог вместо письма."""

from __future__ import annotations

import asyncio
import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import get_settings

logger = logging.getLogger("spi.mail")

# Без таймаута зависшее (не отклонённое, а именно "тишина") TCP-соединение к SMTP
# (например, исходящий порт 587 заблокирован провайдером VPS) вешает весь HTTP-запрос
# POST /auth/request-code бесконечно — пользователь видит "кнопка не отвечает".
# С таймаутом код входа уже создан в БД к этому моменту (см. app/api/auth.py) — при
# ошибке отправки пользователь получит понятный 5xx вместо зависшего запроса.
_SMTP_TIMEOUT_SECONDS = 10


async def send_login_code(email: str, code: str) -> None:
    settings = get_settings()

    if not settings.smtp_host:
        logger.info("[DEV] Login code for %s: %s", email, code)
        return

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = email
    message["Subject"] = "Код входа в SPI Messenger"
    message.set_content(f"Ваш код входа: {code}\nКод действителен 10 минут.")

    try:
        async with asyncio.timeout(_SMTP_TIMEOUT_SECONDS):
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                start_tls=True,
            )
    except (TimeoutError, aiosmtplib.SMTPException):
        logger.exception("Не удалось отправить письмо с кодом входа на %s", email)
        raise
