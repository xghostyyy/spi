"""Догрузка пропущенных сообщений после reconnect (упрощённая версия /sync).

Полноценный event-log с монотонным `seq` — пост-MVP; пока /sync?since=<ISO-время>
возвращает новые сообщения по всем чатам пользователя, чего достаточно, чтобы
не потерять текст, разлив за время обрыва соединения (см. docs/DECISIONS.md, ADR-008).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MessageOut
from app.core.deps import get_current_user
from app.db.models import Chat, ChatMember, Message, User
from app.db.session import get_db
from app.services.chat import build_message_out

router = APIRouter(tags=["sync"])


@router.get("/sync", response_model=list[MessageOut])
async def sync_messages(
    since: datetime = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    chat_ids_result = await db.execute(
        select(ChatMember.chat_id).where(
            ChatMember.user_id == user.id, ChatMember.left_at.is_(None)
        )
    )
    chat_ids = list(chat_ids_result.scalars().all())
    if not chat_ids:
        return []

    result = await db.execute(
        select(Message)
        .where(Message.chat_id.in_(chat_ids), Message.created_at > since)
        .order_by(Message.id)
        .limit(500)
    )
    messages = result.scalars().all()

    chats_by_id = {
        chat.id: chat
        for chat in (await db.execute(select(Chat).where(Chat.id.in_(chat_ids)))).scalars()
    }

    return [
        await build_message_out(db, message, chats_by_id[message.chat_id], user.id)
        for message in messages
    ]
