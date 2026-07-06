"""Фоновая доставка отложенных сообщений (Фаза 6).

Простой поллинг вместо очереди/cron: при одном инстансе API (см.
docs/02-ARCHITECTURE.md §4.2 — Redis/масштабирование пока не требуются) это
самый дешёвый по инфраструктуре способ доставить сообщение в нужное время без
внешнего воркера. Точность — до SCHEDULED_POLL_INTERVAL_SECONDS.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.models import Chat, Message, User
from app.services.chat import build_message_out
from app.services.push import notify_message_sent
from app.ws.events import broadcast_to_chat

logger = logging.getLogger("spi.scheduler")

SCHEDULED_POLL_INTERVAL_SECONDS = 15


async def _deliver_due_message(db: AsyncSession, message: Message) -> None:
    chat_result = await db.execute(select(Chat).where(Chat.id == message.chat_id))
    chat = chat_result.scalar_one()
    sender: User | None = None
    if message.sender_id is not None:
        sender_result = await db.execute(select(User).where(User.id == message.sender_id))
        sender = sender_result.scalar_one_or_none()

    now = datetime.now(UTC)
    message.scheduled_broadcast_at = now
    chat.updated_at = now
    await db.commit()

    out = await build_message_out(db, message, chat, viewer_id=message.sender_id or 0)
    await broadcast_to_chat(db, chat.id, "message.new", out.model_dump(mode="json"))
    if sender is not None:
        await notify_message_sent(db, chat, message, sender)


async def deliver_due_scheduled_messages(db: AsyncSession) -> int:
    """Один проход: рассылает все просроченные ожидающие сообщения. Возвращает их число."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(Message).where(
            Message.scheduled_at.is_not(None),
            Message.scheduled_at <= now,
            Message.scheduled_broadcast_at.is_(None),
            Message.deleted_for_all_at.is_(None),
        )
    )
    messages = result.scalars().all()
    for message in messages:
        await _deliver_due_message(db, message)
    return len(messages)


async def run_scheduler_loop() -> None:
    """Бесконечный цикл — запускается один раз при старте приложения (см. app/main.py)."""
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        while True:
            try:
                async with session_factory() as db:
                    delivered = await deliver_due_scheduled_messages(db)
                    if delivered:
                        logger.info("delivered %d scheduled message(s)", delivered)
            except Exception:
                logger.exception("scheduled message delivery pass failed")
            await asyncio.sleep(SCHEDULED_POLL_INTERVAL_SECONDS)
    finally:
        await engine.dispose()
