"""Web Push: подписки и отправка уведомлений через VAPID (pywebpush)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from pywebpush import WebPushException, webpush
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import ChatMember, PushSubscription
from app.ws.manager import manager

logger = logging.getLogger(__name__)


def _send_one(subscription_info: dict[str, object], payload: str) -> int | None:
    """Синхронный вызов pywebpush (requests внутри) — вызывается через to_thread.

    Возвращает HTTP-статус ошибки при неудаче (например 410 Gone — подписка
    больше не действительна и должна быть удалена), либо None при успехе.
    """
    settings = get_settings()
    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
    except WebPushException as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        logger.warning("push_failed", extra={"status": status_code, "error": str(exc)})
        return status_code
    return None


async def send_push_to_user(
    db: AsyncSession, user_id: int, title: str, body: str, chat_public_id: str
) -> None:
    settings = get_settings()
    if not settings.vapid_private_key or not settings.vapid_public_key:
        return

    result = await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))
    subscriptions = result.scalars().all()
    if not subscriptions:
        return

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "chatPublicId": chat_public_id,
            "icon": "/icons/icon-192.png",
        }
    )
    stale_ids: list[int] = []
    for sub in subscriptions:
        subscription_info: dict[str, object] = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        status_code = await asyncio.to_thread(_send_one, subscription_info, payload)
        if status_code in (404, 410):
            stale_ids.append(sub.id)

    if stale_ids:
        for sub in subscriptions:
            if sub.id in stale_ids:
                await db.delete(sub)
        await db.commit()


async def notify_chat_members(
    db: AsyncSession,
    chat_id: int,
    sender_id: int | None,
    title: str,
    body: str,
    chat_public_id: str,
) -> None:
    """Пуш офлайн-участникам чата (кроме отправителя и заглушивших чат)."""
    result = await db.execute(
        select(ChatMember.user_id).where(
            ChatMember.chat_id == chat_id,
            ChatMember.left_at.is_(None),
            or_(
                ChatMember.muted_until.is_(None),
                ChatMember.muted_until < datetime.now(UTC),
            ),
        )
    )
    member_ids = [uid for uid in result.scalars().all() if uid != sender_id]
    for user_id in member_ids:
        if manager.is_online(user_id):
            continue
        await send_push_to_user(db, user_id, title, body, chat_public_id)
