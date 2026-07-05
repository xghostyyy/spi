"""Рассылка событий участникам чата через ConnectionManager."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMember
from app.ws.manager import manager


async def broadcast_to_chat(
    db: AsyncSession,
    chat_id: int,
    event_type: str,
    payload: object,
    exclude_user_id: int | None = None,
) -> None:
    result = await db.execute(
        select(ChatMember.user_id).where(
            ChatMember.chat_id == chat_id, ChatMember.left_at.is_(None)
        )
    )
    user_ids = [uid for uid in result.scalars().all() if uid != exclude_user_id]
    await manager.send_to_users(user_ids, event_type, payload)
