"""Общая логика чатов/сообщений, переиспользуемая роутерами chats и messages."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.api.schemas import ChatOut, FileOut, MessageOut, ReactionSummary
from app.db.models import (
    Chat,
    ChatMember,
    ChatType,
    File,
    MemberRole,
    Message,
    MessageAttachment,
    MessageBookmark,
    MessageReaction,
    User,
)

CHAT_NOT_FOUND = HTTPException(
    status.HTTP_404_NOT_FOUND, detail={"code": "chat_not_found", "message": "Чат не найден"}
)


async def get_membership_or_404(
    db: AsyncSession, chat_public_id: str, user: User
) -> tuple[Chat, ChatMember]:
    result = await db.execute(select(Chat).where(Chat.public_id == chat_public_id))
    chat = result.scalar_one_or_none()
    if chat is None:
        raise CHAT_NOT_FOUND

    member_result = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat.id,
            ChatMember.user_id == user.id,
            ChatMember.left_at.is_(None),
        )
    )
    member = member_result.scalar_one_or_none()
    if member is None:
        raise CHAT_NOT_FOUND
    return chat, member


async def get_or_create_direct_chat(db: AsyncSession, user_a: User, user_b: User) -> Chat:
    """Находит существующий direct-чат между двумя пользователями либо создаёт новый."""
    existing = await db.execute(
        select(Chat)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .where(Chat.type == ChatType.direct, ChatMember.user_id == user_a.id)
        .where(Chat.id.in_(select(ChatMember.chat_id).where(ChatMember.user_id == user_b.id)))
    )
    chat = existing.scalars().first()
    if chat is not None:
        return chat

    now = datetime.now(UTC)
    chat = Chat(
        public_id=str(ULID()),
        type=ChatType.direct,
        created_at=now,
        updated_at=now,
    )
    db.add(chat)
    await db.flush()

    db.add_all(
        [
            ChatMember(chat_id=chat.id, user_id=user_a.id, joined_at=now),
            ChatMember(chat_id=chat.id, user_id=user_b.id, joined_at=now),
        ]
    )
    await db.flush()
    return chat


async def get_or_create_saved_chat(db: AsyncSession, user: User) -> Chat:
    """Личное «облако» пользователя (Saved Messages) — единственный участник он сам."""
    existing = await db.execute(
        select(Chat)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .where(Chat.type == ChatType.saved, ChatMember.user_id == user.id)
    )
    chat = existing.scalars().first()
    if chat is not None:
        return chat

    now = datetime.now(UTC)
    chat = Chat(
        public_id=str(ULID()),
        type=ChatType.saved,
        owner_id=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(chat)
    await db.flush()

    db.add(ChatMember(chat_id=chat.id, user_id=user.id, role=MemberRole.owner, joined_at=now))
    await db.flush()
    return chat


async def get_direct_peer_user_ids(db: AsyncSession, user_id: int) -> list[int]:
    """ID собеседников по всем direct-чатам пользователя (для рассылки presence)."""
    my_chat_ids = select(ChatMember.chat_id).where(ChatMember.user_id == user_id)
    result = await db.execute(
        select(ChatMember.user_id)
        .join(Chat, Chat.id == ChatMember.chat_id)
        .where(
            Chat.type == ChatType.direct,
            ChatMember.user_id != user_id,
            ChatMember.chat_id.in_(my_chat_ids),
        )
    )
    return list(result.scalars().all())


async def get_peer_member(db: AsyncSession, chat: Chat, user_id: int) -> ChatMember | None:
    """Для direct-чата — членство собеседника (не текущего пользователя)."""
    if chat.type != ChatType.direct:
        return None
    result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat.id, ChatMember.user_id != user_id)
    )
    return result.scalar_one_or_none()


async def get_last_message(db: AsyncSession, chat_id: int) -> Message | None:
    result = await db.execute(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.id.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def count_unread(
    db: AsyncSession, chat_id: int, viewer_id: int, last_read_id: int | None
) -> int:
    stmt = select(func.count(Message.id)).where(
        Message.chat_id == chat_id, Message.sender_id != viewer_id
    )
    if last_read_id is not None:
        stmt = stmt.where(Message.id > last_read_id)
    result = await db.execute(stmt)
    return int(result.scalar_one())


async def get_reactions_summary(
    db: AsyncSession, message_id: int, viewer_id: int
) -> list[dict[str, object]]:
    result = await db.execute(
        select(MessageReaction.emoji, MessageReaction.user_id).where(
            MessageReaction.message_id == message_id
        )
    )
    counts: dict[str, int] = {}
    mine: set[str] = set()
    for emoji, user_id in result.all():
        counts[emoji] = counts.get(emoji, 0) + 1
        if user_id == viewer_id:
            mine.add(emoji)
    return [
        {"emoji": emoji, "count": count, "reacted_by_me": emoji in mine}
        for emoji, count in counts.items()
    ]


async def message_status(db: AsyncSession, message: Message, chat: Chat, viewer_id: int) -> str:
    """'read' | 'sent' — актуально только для собственных сообщений viewer'а."""
    if message.sender_id != viewer_id:
        return "sent"
    peer = await get_peer_member(db, chat, viewer_id)
    if peer is not None and peer.last_read_message_id is not None:
        if peer.last_read_message_id >= message.id:
            return "read"
    return "sent"


async def avatar_url_for(db: AsyncSession, avatar_file_id: int | None) -> str | None:
    if not avatar_file_id:
        return None
    result = await db.execute(select(File.storage_key).where(File.id == avatar_file_id))
    key = result.scalar_one_or_none()
    return f"/media/{key}" if key else None


async def get_attachments(db: AsyncSession, message_id: int) -> list[FileOut]:
    result = await db.execute(
        select(File)
        .join(MessageAttachment, MessageAttachment.file_id == File.id)
        .where(MessageAttachment.message_id == message_id)
        .order_by(MessageAttachment.position)
    )
    return [FileOut.from_model(file) for file in result.scalars().all()]


async def build_message_out(
    db: AsyncSession, message: Message, chat: Chat, viewer_id: int
) -> MessageOut:
    sender_public_id = None
    if message.sender_id:
        sender_result = await db.execute(select(User.public_id).where(User.id == message.sender_id))
        sender_public_id = sender_result.scalar_one_or_none()

    reply_to_public_id = None
    if message.reply_to_id:
        reply_result = await db.execute(
            select(Message.public_id).where(Message.id == message.reply_to_id)
        )
        reply_to_public_id = reply_result.scalar_one_or_none()

    reactions = await get_reactions_summary(db, message.id, viewer_id)
    status_value = await message_status(db, message, chat, viewer_id)
    is_deleted = message.deleted_for_all_at is not None
    attachments = [] if is_deleted else await get_attachments(db, message.id)

    bookmark_result = await db.execute(
        select(MessageBookmark).where(
            MessageBookmark.message_id == message.id, MessageBookmark.user_id == viewer_id
        )
    )
    bookmarked = bookmark_result.scalar_one_or_none() is not None

    return MessageOut(
        message_public_id=message.public_id,
        chat_public_id=chat.public_id,
        sender_public_id=sender_public_id,
        type=message.type,
        body=None if is_deleted else message.body,
        reply_to_public_id=reply_to_public_id,
        edited_at=message.edited_at,
        deleted_for_all=is_deleted,
        created_at=message.created_at,
        status=status_value,
        reactions=[ReactionSummary(**r) for r in reactions],
        attachments=attachments,
        bookmarked=bookmarked,
    )


async def build_chat_out(db: AsyncSession, chat: Chat, member: ChatMember, viewer: User) -> ChatOut:
    peer_public_id: str | None = None
    peer_username: str | None = None
    peer_last_seen_at: datetime | None = None
    avatar_url: str | None

    if chat.type == ChatType.direct:
        peer_member = await get_peer_member(db, chat, viewer.id)
        peer: User | None = None
        if peer_member is not None:
            peer_result = await db.execute(select(User).where(User.id == peer_member.user_id))
            peer = peer_result.scalar_one_or_none()
        title = peer.display_name if peer else "Диалог"
        avatar_url = await avatar_url_for(db, peer.avatar_file_id) if peer else None
        if peer is not None:
            peer_public_id = peer.public_id
            peer_username = peer.username
            peer_last_seen_at = peer.last_seen_at
    else:
        title = chat.title or ""
        avatar_url = await avatar_url_for(db, chat.avatar_file_id)

    last_message = await get_last_message(db, chat.id)
    last_message_out = (
        await build_message_out(db, last_message, chat, viewer.id) if last_message else None
    )
    unread = await count_unread(db, chat.id, viewer.id, member.last_read_message_id)

    return ChatOut(
        chat_public_id=chat.public_id,
        type=chat.type.value,
        title=title,
        avatar_url=avatar_url,
        is_pinned=member.is_pinned,
        is_archived=member.is_archived,
        muted_until=member.muted_until,
        unread_count=unread,
        last_message=last_message_out,
        peer_public_id=peer_public_id,
        peer_username=peer_username,
        peer_online=False,
        peer_last_seen_at=peer_last_seen_at,
    )
