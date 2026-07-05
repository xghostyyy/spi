"""Глобальный поиск: чаты (по имени/username собеседника) и сообщения (полнотекстовый)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.schemas import ChatOut, MessageOut
from app.core.deps import get_current_user
from app.db.models import Chat, ChatMember, ChatType, Message, User
from app.db.session import get_db
from app.services.chat import build_chat_out, build_message_out

router = APIRouter(prefix="/search", tags=["search"])


class SearchResult(BaseModel):
    chats: list[ChatOut]
    messages: list[MessageOut]


@router.get("", response_model=SearchResult)
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResult:
    pattern = f"%{q}%"

    peer_member = aliased(ChatMember)
    chats_result = await db.execute(
        select(Chat, ChatMember)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .join(
            peer_member,
            and_(peer_member.chat_id == Chat.id, peer_member.user_id != user.id),
        )
        .join(User, User.id == peer_member.user_id)
        .where(
            ChatMember.user_id == user.id,
            ChatMember.left_at.is_(None),
            Chat.type == ChatType.direct,
            or_(User.display_name.ilike(pattern), User.username.ilike(pattern)),
        )
        .limit(20)
    )
    chats_out = [
        await build_chat_out(db, chat, member, user) for chat, member in chats_result.all()
    ]

    my_chat_ids = select(ChatMember.chat_id).where(
        ChatMember.user_id == user.id, ChatMember.left_at.is_(None)
    )
    messages_result = await db.execute(
        select(Message)
        .where(
            Message.chat_id.in_(my_chat_ids),
            Message.deleted_for_all_at.is_(None),
            Message.search_tsv.op("@@")(func.plainto_tsquery("russian", q)),
        )
        .order_by(Message.id.desc())
        .limit(50)
    )
    messages = messages_result.scalars().all()

    chats_by_id: dict[int, Chat] = {}
    if messages:
        involved_chat_ids = {m.chat_id for m in messages}
        involved_result = await db.execute(select(Chat).where(Chat.id.in_(involved_chat_ids)))
        chats_by_id = {chat.id: chat for chat in involved_result.scalars().all()}

    messages_out = [
        await build_message_out(db, message, chats_by_id[message.chat_id], user.id)
        for message in messages
    ]

    return SearchResult(chats=chats_out, messages=messages_out)
