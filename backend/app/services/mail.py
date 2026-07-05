"""Отправка e-mail. В dev (без SMTP) код входа пишется в лог вместо письма."""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import get_settings

logger = logging.getLogger("spi.mail")


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

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=True,
    )
