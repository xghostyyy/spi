"""Личные закладки на сообщения (флажок) — независимо от Saved Messages."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MessageOut
from app.core.deps import get_current_user
from app.db.models import Chat, ChatMember, Message, MessageBookmark, User
from app.db.session import get_db
from app.services.chat import build_message_out

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])

_MESSAGE_NOT_FOUND = HTTPException(
    status.HTTP_404_NOT_FOUND,
    detail={"code": "message_not_found", "message": "Сообщение не найдено"},
)


@router.get("", response_model=list[MessageOut])
async def list_bookmarks(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[MessageOut]:
    result = await db.execute(
        select(Message)
        .join(MessageBookmark, MessageBookmark.message_id == Message.id)
        .where(MessageBookmark.user_id == user.id)
        .order_by(MessageBookmark.created_at.desc())
    )
    messages = result.scalars().all()
    if not messages:
        return []

    chat_ids = {m.chat_id for m in messages}
    chats_result = await db.execute(select(Chat).where(Chat.id.in_(chat_ids)))
    chats_by_id = {chat.id: chat for chat in chats_result.scalars().all()}

    return [
        await build_message_out(db, message, chats_by_id[message.chat_id], user.id)
        for message in messages
    ]


@router.post("/{message_public_id}")
async def toggle_bookmark(
    message_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    message_result = await db.execute(select(Message).where(Message.public_id == message_public_id))
    message = message_result.scalar_one_or_none()
    if message is None:
        raise _MESSAGE_NOT_FOUND

    member_result = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == message.chat_id,
            ChatMember.user_id == user.id,
            ChatMember.left_at.is_(None),
        )
    )
    if member_result.scalar_one_or_none() is None:
        raise _MESSAGE_NOT_FOUND

    existing_result = await db.execute(
        select(MessageBookmark).where(
            MessageBookmark.message_id == message.id, MessageBookmark.user_id == user.id
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        await db.delete(existing)
        await db.commit()
        return {"bookmarked": False}

    stmt = (
        pg_insert(MessageBookmark)
        .values(user_id=user.id, message_id=message.id, created_at=datetime.now(UTC))
        .on_conflict_do_nothing(index_elements=["user_id", "message_id"])
    )
    await db.execute(stmt)
    await db.commit()
    return {"bookmarked": True}
