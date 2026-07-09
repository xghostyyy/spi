"""Групповые чаты: создание, участники, права, системные события."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.api.schemas import ChatInviteOut, ChatMemberOut, ChatOut, InvitePreviewOut, MessageOut
from app.core.deps import get_current_user
from app.db.models import Chat, ChatInvite, ChatMember, ChatType, MemberRole, Message, User
from app.db.session import get_db
from app.services.chat import (
    FORBIDDEN,
    INVITE_EXPIRED,
    INVITE_NOT_FOUND,
    MESSAGE_NOT_FOUND,
    NOT_A_GROUP,
    add_or_reactivate_members,
    avatar_url_for,
    build_chat_out,
    count_members,
    create_invite,
    create_system_message,
    get_invite_by_token,
    get_member_by_public_id,
    get_membership_or_404,
    invite_is_valid,
    join_chat_via_invite,
    list_chat_members,
    list_pinned_messages,
    pin_message,
    require_permission,
    unpin_message,
)
from app.ws.events import broadcast_to_chat

router = APIRouter(prefix="/chats", tags=["groups"])
invite_router = APIRouter(prefix="/invites", tags=["groups"])

_MAX_INVITE_EXPIRY_HOURS = 24 * 30

_MAX_MEMBERS_PER_REQUEST = 50


class CreateGroupBody(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    member_usernames: list[str] = Field(default_factory=list)


class CreateChannelBody(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)


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


class CreateInviteBody(BaseModel):
    max_uses: int | None = Field(default=None, ge=1)
    expires_in_hours: int | None = Field(default=None, ge=1, le=_MAX_INVITE_EXPIRY_HOURS)


def _invite_out(invite: ChatInvite, chat_public_id: str) -> ChatInviteOut:
    return ChatInviteOut(
        token=invite.token,
        chat_public_id=chat_public_id,
        max_uses=invite.max_uses,
        used_count=invite.used_count,
        expires_at=invite.expires_at,
        revoked_at=invite.revoked_at,
        created_at=invite.created_at,
    )


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


@router.post("/channel", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_channel(
    body: CreateChannelBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    now = datetime.now(UTC)
    chat = Chat(
        public_id=str(ULID()),
        type=ChatType.group,
        is_channel=True,
        title=body.title.strip(),
        description=body.description.strip() if body.description else None,
        owner_id=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(chat)
    await db.flush()

    db.add(ChatMember(chat_id=chat.id, user_id=user.id, role=MemberRole.owner, joined_at=now))
    await db.commit()

    member_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat.id, ChatMember.user_id == user.id)
    )
    member = member_result.scalar_one()

    await create_system_message(
        db, chat, "channel_created", {"actor": user.public_id, "title": chat.title}
    )

    return await build_chat_out(db, chat, member, user)


@router.get("/{chat_public_id}/members", response_model=list[ChatMemberOut])
async def get_group_members(
    chat_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMemberOut]:
    chat, member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)
    members = await list_chat_members(db, chat.id)
    if chat.is_channel and member.role == MemberRole.member:
        # Обычные подписчики канала не видят список друг друга (приватность) —
        # только владельца/админов, как в Telegram (см. ADR-022).
        return [m for m in members if m.role in ("owner", "admin")]
    return members


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


@router.post(
    "/{chat_public_id}/invites", response_model=ChatInviteOut, status_code=status.HTTP_201_CREATED
)
async def create_group_invite(
    chat_public_id: str,
    body: CreateInviteBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatInviteOut:
    chat, member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)
    require_permission(member, "can_invite")

    expires_at = (
        datetime.now(UTC) + timedelta(hours=body.expires_in_hours)
        if body.expires_in_hours
        else None
    )
    invite = await create_invite(db, chat, user, body.max_uses, expires_at)
    await db.commit()
    return _invite_out(invite, chat.public_id)


@router.get("/{chat_public_id}/invites", response_model=list[ChatInviteOut])
async def list_group_invites(
    chat_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatInviteOut]:
    chat, member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)
    require_permission(member, "can_invite")

    result = await db.execute(
        select(ChatInvite)
        .where(ChatInvite.chat_id == chat.id)
        .order_by(ChatInvite.created_at.desc())
    )
    return [_invite_out(invite, chat.public_id) for invite in result.scalars().all()]


@router.delete("/{chat_public_id}/invites/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_group_invite(
    chat_public_id: str,
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    chat, member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)
    require_permission(member, "can_invite")

    invite = await get_invite_by_token(db, token)
    if invite is None or invite.chat_id != chat.id:
        raise INVITE_NOT_FOUND
    invite.revoked_at = datetime.now(UTC)
    await db.commit()


@invite_router.get("/{token}", response_model=InvitePreviewOut)
async def preview_invite(token: str, db: AsyncSession = Depends(get_db)) -> InvitePreviewOut:
    invite = await get_invite_by_token(db, token)
    if invite is None:
        raise INVITE_NOT_FOUND

    chat_result = await db.execute(select(Chat).where(Chat.id == invite.chat_id))
    chat = chat_result.scalar_one()
    member_count = await count_members(db, chat.id)
    return InvitePreviewOut(
        chat_title=chat.title or "",
        chat_description=chat.description,
        member_count=member_count,
        avatar_url=await avatar_url_for(db, chat.avatar_file_id),
        valid=invite_is_valid(invite),
    )


@invite_router.post("/{token}/join", response_model=ChatOut)
async def join_via_invite(
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    invite = await get_invite_by_token(db, token)
    if invite is None:
        raise INVITE_NOT_FOUND
    if not invite_is_valid(invite):
        raise INVITE_EXPIRED

    chat_result = await db.execute(select(Chat).where(Chat.id == invite.chat_id))
    chat = chat_result.scalar_one()
    is_new = (
        await db.execute(
            select(ChatMember).where(ChatMember.chat_id == chat.id, ChatMember.user_id == user.id)
        )
    ).scalar_one_or_none() is None

    member = await join_chat_via_invite(db, invite, chat, user)
    await db.commit()

    if is_new:
        await create_system_message(db, chat, "member_joined_via_invite", {"actor": user.public_id})

    return await build_chat_out(db, chat, member, user)


@router.get("/{chat_public_id}/pinned", response_model=list[MessageOut])
async def get_pinned_messages(
    chat_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)
    return await list_pinned_messages(db, chat, user.id)


@router.post(
    "/{chat_public_id}/messages/{message_public_id}/pin", status_code=status.HTTP_204_NO_CONTENT
)
async def pin_group_message(
    chat_public_id: str,
    message_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    chat, member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)
    require_permission(member, "can_pin")

    message_result = await db.execute(
        select(Message).where(Message.public_id == message_public_id, Message.chat_id == chat.id)
    )
    message = message_result.scalar_one_or_none()
    if message is None:
        raise MESSAGE_NOT_FOUND

    await pin_message(db, chat, message, user)
    await create_system_message(
        db, chat, "message_pinned", {"actor": user.public_id, "message": message_public_id}
    )
    pinned = await list_pinned_messages(db, chat, user.id)
    await broadcast_to_chat(
        db,
        chat.id,
        "pinned.updated",
        {"chat_public_id": chat.public_id, "pinned": [m.model_dump(mode="json") for m in pinned]},
    )


@router.delete(
    "/{chat_public_id}/messages/{message_public_id}/pin", status_code=status.HTTP_204_NO_CONTENT
)
async def unpin_group_message(
    chat_public_id: str,
    message_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    chat, member = await get_membership_or_404(db, chat_public_id, user)
    _require_group(chat)
    require_permission(member, "can_pin")

    message_result = await db.execute(
        select(Message).where(Message.public_id == message_public_id, Message.chat_id == chat.id)
    )
    message = message_result.scalar_one_or_none()
    if message is None:
        raise MESSAGE_NOT_FOUND

    await unpin_message(db, chat.id, message.id)
    pinned = await list_pinned_messages(db, chat, user.id)
    await broadcast_to_chat(
        db,
        chat.id,
        "pinned.updated",
        {"chat_public_id": chat.public_id, "pinned": [m.model_dump(mode="json") for m in pinned]},
    )
