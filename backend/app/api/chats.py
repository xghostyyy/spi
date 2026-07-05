"""Список личных чатов: создание, закреп/архив/mute."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ChatOut
from app.core.deps import get_current_user
from app.db.models import Chat, ChatMember, User
from app.db.session import get_db
from app.services.chat import (
    build_chat_out,
    get_membership_or_404,
    get_or_create_direct_chat,
    get_or_create_saved_chat,
)

router = APIRouter(prefix="/chats", tags=["chats"])


class CreateDirectChatBody(BaseModel):
    username: str


class UpdateChatMembershipBody(BaseModel):
    is_pinned: bool | None = None
    is_archived: bool | None = None
    muted_until: datetime | None = None
    mute_forever: bool | None = None


@router.get("", response_model=list[ChatOut])
async def list_chats(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ChatOut]:
    result = await db.execute(
        select(ChatMember)
        .where(ChatMember.user_id == user.id, ChatMember.left_at.is_(None))
        .order_by(ChatMember.is_pinned.desc())
    )
    memberships = result.scalars().all()

    chats_out = []
    for member in memberships:
        chat_result = await db.execute(select(Chat).where(Chat.id == member.chat_id))
        chat = chat_result.scalar_one()
        chats_out.append(await build_chat_out(db, chat, member, user))

    chats_out.sort(
        key=lambda c: c.last_message.created_at if c.last_message else datetime.min,
        reverse=True,
    )
    chats_out.sort(key=lambda c: c.is_pinned, reverse=True)
    return chats_out


@router.post("", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_direct_chat(
    body: CreateDirectChatBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    username = body.username.strip().lstrip("@")
    if username == user.username:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "self_chat", "message": "Нельзя создать чат с самим собой"},
        )
    target_result = await db.execute(select(User).where(User.username == username))
    target = target_result.scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "Пользователь не найден"},
        )

    chat = await get_or_create_direct_chat(db, user, target)
    await db.commit()

    member_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat.id, ChatMember.user_id == user.id)
    )
    member = member_result.scalar_one()
    return await build_chat_out(db, chat, member, user)


@router.get("/saved", response_model=ChatOut)
async def get_saved_chat(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ChatOut:
    chat = await get_or_create_saved_chat(db, user)
    await db.commit()

    member_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat.id, ChatMember.user_id == user.id)
    )
    member = member_result.scalar_one()
    return await build_chat_out(db, chat, member, user)


@router.patch("/{chat_public_id}", response_model=ChatOut)
async def update_chat_membership(
    chat_public_id: str,
    body: UpdateChatMembershipBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat, member = await get_membership_or_404(db, chat_public_id, user)

    if body.is_pinned is not None:
        member.is_pinned = body.is_pinned
    if body.is_archived is not None:
        member.is_archived = body.is_archived
    if body.mute_forever:
        member.muted_until = datetime.max.replace(tzinfo=UTC)
    elif body.muted_until is not None:
        member.muted_until = body.muted_until
    elif "muted_until" in body.model_fields_set and body.muted_until is None:
        member.muted_until = None

    await db.commit()
    return await build_chat_out(db, chat, member, user)
