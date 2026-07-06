"""Групповые чаты: создание, участники, права, системные события."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.api.schemas import ChatMemberOut, ChatOut
from app.core.deps import get_current_user
from app.db.models import Chat, ChatMember, ChatType, MemberRole, User
from app.db.session import get_db
from app.services.chat import (
    FORBIDDEN,
    NOT_A_GROUP,
    add_or_reactivate_members,
    build_chat_out,
    count_members,
    create_system_message,
    get_member_by_public_id,
    get_membership_or_404,
    list_chat_members,
    require_permission,
)

router = APIRouter(prefix="/chats", tags=["groups"])

_MAX_MEMBERS_PER_REQUEST = 50


class CreateGroupBody(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    member_usernames: list[str] = Field(default_factory=list)


class AddMembersBody(BaseModel):
    usernames: list[str] = Field(min_length=1, max_length=_MAX_MEMBERS_PER_REQUEST)


class UpdateMemberBody(BaseModel):
    role: str | None = None
    can_delete_messages: bool | None = None
    can_ban: bool | None = None
    can_invite: bool | None = None
    can_pin: bool | None = None
    can_edit_info: bool | None = None


class UpdateGroupInfoBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)


async def _resolve_usernames(
    db: AsyncSession, usernames: list[str], exclude_user_id: int
) -> list[User]:
    cleaned = {u.strip().lstrip("@") for u in usernames if u.strip()}
    if not cleaned:
        return []
    result = await db.execute(select(User).where(User.username.in_(cleaned)))
    return [u for u in result.scalars().all() if u.id != exclude_user_id]


def _require_group(chat: Chat) -> None:
    if chat.type != ChatType.group:
        raise NOT_A_GROUP


@router.post("/group", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: CreateGroupBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    now = datetime.now(UTC)
    chat = Chat(
        public_id=str(ULID()),
        type=ChatType.group,
        title=body.title.strip(),
        description=body.description.strip() if body.description else None,
        owner_id=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(chat)
    await db.flush()

    db.add(ChatMember(chat_id=chat.id, user_id=user.id, role=MemberRole.owner, joined_at=now))

    candidates = await _resolve_usernames(db, body.member_usernames, user.id)
    added = await add_or_reactivate_members(db, chat.id, candidates, now)

    await db.commit()

    member_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat.id, ChatMember.user_id == user.id)
    )
    member = member_result.scalar_one()

    await create_system_message(
        db, chat, "group_created", {"actor": user.public_id, "title": chat.title}
    )
    for added_user in added:
        await create_system_message(
            db, chat, "member_added", {"actor": user.public_id, "target": added_user.public_id}
        )

    return await build_chat_out(db, chat, member, user)


@router.get("/{chat_public_id}/members", response_model=list[ChatMemberOut])
async def get_group_members(
    chat_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMemberOut]:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)
    return await list_chat_members(db, chat.id)


@router.post(
    "/{chat_public_id}/members",
    response_model=list[ChatMemberOut],
    status_code=status.HTTP_201_CREATED,
)
async def add_group_members(
    chat_public_id: str,
    body: AddMembersBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMemberOut]:
    chat, member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)
    require_permission(member, "can_invite")

    candidates = await _resolve_usernames(db, body.usernames, user.id)
    now = datetime.now(UTC)
    added = await add_or_reactivate_members(db, chat.id, candidates, now)
    await db.commit()

    for added_user in added:
        await create_system_message(
            db, chat, "member_added", {"actor": user.public_id, "target": added_user.public_id}
        )

    return await list_chat_members(db, chat.id)


@router.delete("/{chat_public_id}/members/{user_public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    chat_public_id: str,
    user_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    chat, member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)

    if user_public_id == user.public_id:
        if member.role == MemberRole.owner:
            total = await count_members(db, chat.id)
            if total > 1:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "owner_must_transfer",
                        "message": "Сначала передайте права владельца другому участнику",
                    },
                )
        member.left_at = datetime.now(UTC)
        await db.commit()
        await create_system_message(db, chat, "member_left", {"actor": user.public_id})
        return

    require_permission(member, "can_ban")
    target = await get_member_by_public_id(db, chat.id, user_public_id)
    if target is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "member_not_found", "message": "Участник не найден"},
        )
    target_member, target_user = target
    if target_member.role == MemberRole.owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "cannot_remove_owner", "message": "Нельзя удалить владельца"},
        )

    now = datetime.now(UTC)
    target_member.left_at = now
    target_member.banned_at = now
    await db.commit()
    await create_system_message(
        db, chat, "member_removed", {"actor": user.public_id, "target": target_user.public_id}
    )


@router.patch("/{chat_public_id}/members/{user_public_id}", response_model=ChatMemberOut)
async def update_group_member(
    chat_public_id: str,
    user_public_id: str,
    body: UpdateMemberBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMemberOut:
    chat, member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)
    if member.role != MemberRole.owner:
        raise FORBIDDEN

    if user_public_id == user.public_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "cannot_edit_self", "message": "Нельзя изменить свою роль"},
        )

    target = await get_member_by_public_id(db, chat.id, user_public_id)
    if target is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "member_not_found", "message": "Участник не найден"},
        )
    target_member, _target_user = target

    if body.role is not None:
        if body.role not in ("admin", "member"):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "invalid_role", "message": "Недопустимая роль"},
            )
        target_member.role = MemberRole(body.role)
    for field in ("can_delete_messages", "can_ban", "can_invite", "can_pin", "can_edit_info"):
        value = getattr(body, field)
        if value is not None:
            setattr(target_member, field, value)

    await db.commit()
    await create_system_message(
        db, chat, "role_changed", {"actor": user.public_id, "target": user_public_id}
    )

    members = await list_chat_members(db, chat.id)
    for member_out in members:
        if member_out.user_public_id == user_public_id:
            return member_out
    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={"code": "member_not_found", "message": "Участник не найден"},
    )


@router.patch("/{chat_public_id}/info", response_model=ChatOut)
async def update_group_info(
    chat_public_id: str,
    body: UpdateGroupInfoBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat, member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)
    require_permission(member, "can_edit_info")

    changed = False
    if body.title is not None and body.title.strip() != chat.title:
        chat.title = body.title.strip()
        changed = True
    if "description" in body.model_fields_set:
        new_description = body.description.strip() if body.description else None
        if new_description != chat.description:
            chat.description = new_description
            changed = True

    if changed:
        chat.updated_at = datetime.now(UTC)
    await db.commit()
    if changed:
        await create_system_message(db, chat, "info_updated", {"actor": user.public_id})

    return await build_chat_out(db, chat, member, user)
