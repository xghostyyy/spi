"""Общая логика чатов/сообщений, переиспользуемая роутерами chats и messages."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.api.schemas import ChatMemberOut, ChatOut, FileOut, MessageOut, ReactionSummary
from app.core.security import generate_invite_token
from app.db.models import (
    Chat,
    ChatInvite,
    ChatMember,
    ChatType,
    File,
    MemberRole,
    Message,
    MessageAttachment,
    MessageBookmark,
    MessageReaction,
    MessageType,
    PinnedMessage,
    User,
)
from app.ws.events import broadcast_to_chat
from app.ws.manager import manager

CHAT_NOT_FOUND = HTTPException(
    status.HTTP_404_NOT_FOUND, detail={"code": "chat_not_found", "message": "Чат не найден"}
)
FORBIDDEN = HTTPException(
    status.HTTP_403_FORBIDDEN, detail={"code": "forbidden", "message": "Недостаточно прав"}
)
NOT_A_GROUP = HTTPException(
    status.HTTP_400_BAD_REQUEST, detail={"code": "not_a_group", "message": "Не групповой чат"}
)
INVITE_NOT_FOUND = HTTPException(
    status.HTTP_404_NOT_FOUND,
    detail={"code": "invite_not_found", "message": "Ссылка недействительна"},
)
INVITE_EXPIRED = HTTPException(
    status.HTTP_410_GONE, detail={"code": "invite_expired", "message": "Ссылка больше не активна"}
)
BANNED_FROM_CHAT = HTTPException(
    status.HTTP_403_FORBIDDEN,
    detail={"code": "banned_from_chat", "message": "Вы были удалены из этого чата"},
)
MESSAGE_NOT_FOUND = HTTPException(
    status.HTTP_404_NOT_FOUND,
    detail={"code": "message_not_found", "message": "Сообщение не найдено"},
)

_ADMIN_PERMISSIONS = frozenset(
    {"can_delete_messages", "can_ban", "can_invite", "can_pin", "can_edit_info"}
)


def has_permission(member: ChatMember, permission: str) -> bool:
    if member.role == MemberRole.owner:
        return True
    if member.role != MemberRole.admin or permission not in _ADMIN_PERMISSIONS:
        return False
    return bool(getattr(member, permission))


def require_permission(member: ChatMember, permission: str) -> None:
    if not has_permission(member, permission):
        raise FORBIDDEN


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


async def get_member_by_public_id(
    db: AsyncSession, chat_id: int, user_public_id: str
) -> tuple[ChatMember, User] | None:
    result = await db.execute(
        select(ChatMember, User)
        .join(User, User.id == ChatMember.user_id)
        .where(
            ChatMember.chat_id == chat_id,
            User.public_id == user_public_id,
            ChatMember.left_at.is_(None),
        )
    )
    row = result.first()
    return (row[0], row[1]) if row is not None else None


async def list_chat_members(db: AsyncSession, chat_id: int) -> list[ChatMemberOut]:
    result = await db.execute(
        select(ChatMember, User)
        .join(User, User.id == ChatMember.user_id)
        .where(ChatMember.chat_id == chat_id, ChatMember.left_at.is_(None))
        .order_by(ChatMember.role, User.display_name)
    )
    members_out = []
    for member, member_user in result.all():
        members_out.append(
            ChatMemberOut(
                user_public_id=member_user.public_id,
                username=member_user.username,
                display_name=member_user.display_name,
                avatar_url=await avatar_url_for(db, member_user.avatar_file_id),
                role=member.role.value,
                can_delete_messages=member.can_delete_messages,
                can_ban=member.can_ban,
                can_invite=member.can_invite,
                can_pin=member.can_pin,
                can_edit_info=member.can_edit_info,
                online=manager.is_online(member_user.id),
                last_seen_at=member_user.last_seen_at,
            )
        )
    return members_out


async def add_or_reactivate_members(
    db: AsyncSession, chat_id: int, candidates: list[User], now: datetime
) -> list[User]:
    """Добавляет пользователей в группу; для тех, кто ранее вышел/был удалён — реактивирует
    существующую строку ChatMember (нельзя вставить вторую из-за UNIQUE(chat_id, user_id))."""
    added: list[User] = []
    for candidate in candidates:
        existing_result = await db.execute(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id, ChatMember.user_id == candidate.id
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            if existing.left_at is None:
                continue
            existing.left_at = None
            existing.banned_at = None
            existing.role = MemberRole.member
            existing.joined_at = now
        else:
            db.add(ChatMember(chat_id=chat_id, user_id=candidate.id, joined_at=now))
        added.append(candidate)
    return added


async def create_invite(
    db: AsyncSession,
    chat: Chat,
    creator: User,
    max_uses: int | None,
    expires_at: datetime | None,
) -> ChatInvite:
    invite = ChatInvite(
        chat_id=chat.id,
        token=generate_invite_token(),
        created_by=creator.id,
        max_uses=max_uses,
        used_count=0,
        expires_at=expires_at,
        created_at=datetime.now(UTC),
    )
    db.add(invite)
    await db.flush()
    return invite


async def get_invite_by_token(db: AsyncSession, token: str) -> ChatInvite | None:
    result = await db.execute(select(ChatInvite).where(ChatInvite.token == token))
    return result.scalar_one_or_none()


def invite_is_valid(invite: ChatInvite) -> bool:
    if invite.revoked_at is not None:
        return False
    if invite.expires_at is not None and invite.expires_at <= datetime.now(UTC):
        return False
    return not (invite.max_uses is not None and invite.used_count >= invite.max_uses)


async def join_chat_via_invite(
    db: AsyncSession, invite: ChatInvite, chat: Chat, user: User
) -> ChatMember:
    existing_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat.id, ChatMember.user_id == user.id)
    )
    existing = existing_result.scalar_one_or_none()
    now = datetime.now(UTC)

    if existing is not None and existing.left_at is None:
        return existing
    if existing is not None and existing.banned_at is not None:
        raise BANNED_FROM_CHAT

    if existing is not None:
        existing.left_at = None
        existing.role = MemberRole.member
        existing.joined_at = now
        member = existing
    else:
        member = ChatMember(chat_id=chat.id, user_id=user.id, joined_at=now)
        db.add(member)

    invite.used_count += 1
    await db.flush()
    return member


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


async def count_members(db: AsyncSession, chat_id: int) -> int:
    result = await db.execute(
        select(func.count(ChatMember.id)).where(
            ChatMember.chat_id == chat_id, ChatMember.left_at.is_(None)
        )
    )
    return int(result.scalar_one())


async def count_unread_mentions(
    db: AsyncSession,
    chat_id: int,
    viewer_id: int,
    username: str | None,
    last_read_id: int | None,
) -> int:
    if not username:
        return 0
    stmt = select(func.count(Message.id)).where(
        Message.chat_id == chat_id,
        Message.sender_id != viewer_id,
        Message.body.ilike(f"%@{username}%"),
    )
    if last_read_id is not None:
        stmt = stmt.where(Message.id > last_read_id)
    result = await db.execute(stmt)
    return int(result.scalar_one())


async def create_system_message(
    db: AsyncSession, chat: Chat, event: str, payload: dict[str, object]
) -> None:
    """Системное сообщение о событии в группе («X добавил Y» и т.п.), с рассылкой по WS.

    Вставка через Core insert(), а не ORM-конструктор Message(...): последний включает
    в INSERT все смаппленные колонки, включая generated-колонку search_tsv, а Postgres
    запрещает вставлять в неё явное значение (см. messages.py::send_message — тот же
    паттерн уже используется там по этой же причине)."""
    now = datetime.now(UTC)
    insert_stmt = (
        pg_insert(Message)
        .values(
            public_id=str(ULID()),
            chat_id=chat.id,
            sender_id=None,
            type=MessageType.system,
            payload={"event": event, **payload},
            created_at=now,
        )
        .returning(Message.id)
    )
    result = await db.execute(insert_stmt)
    message_id = result.scalar_one()
    chat.updated_at = now
    await db.commit()

    message_result = await db.execute(select(Message).where(Message.id == message_id))
    message = message_result.scalar_one()

    out = await build_message_out(db, message, chat, viewer_id=0)
    await broadcast_to_chat(db, chat.id, "message.new", out.model_dump(mode="json"))


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

    forwarded_from_user_public_id = None
    if message.forwarded_from_user_id:
        forwarded_user_result = await db.execute(
            select(User.public_id).where(User.id == message.forwarded_from_user_id)
        )
        forwarded_from_user_public_id = forwarded_user_result.scalar_one_or_none()

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
        payload=None if is_deleted else message.payload,
        reply_to_public_id=reply_to_public_id,
        forwarded_from_user_public_id=forwarded_from_user_public_id,
        edited_at=message.edited_at,
        deleted_for_all=is_deleted,
        created_at=message.created_at,
        status=status_value,
        reactions=[ReactionSummary(**r) for r in reactions],
        attachments=attachments,
        bookmarked=bookmarked,
    )


async def list_pinned_messages(db: AsyncSession, chat: Chat, viewer_id: int) -> list[MessageOut]:
    result = await db.execute(
        select(Message)
        .join(PinnedMessage, PinnedMessage.message_id == Message.id)
        .where(PinnedMessage.chat_id == chat.id)
        .order_by(PinnedMessage.pinned_at.desc())
    )
    return [await build_message_out(db, message, chat, viewer_id) for message in result.scalars()]


async def pin_message(db: AsyncSession, chat: Chat, message: Message, user: User) -> None:
    stmt = (
        pg_insert(PinnedMessage)
        .values(
            chat_id=chat.id,
            message_id=message.id,
            pinned_by=user.id,
            pinned_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["chat_id", "message_id"])
    )
    await db.execute(stmt)
    await db.commit()


async def unpin_message(db: AsyncSession, chat_id: int, message_id: int) -> None:
    result = await db.execute(
        select(PinnedMessage).where(
            PinnedMessage.chat_id == chat_id, PinnedMessage.message_id == message_id
        )
    )
    pinned = result.scalar_one_or_none()
    if pinned is None:
        return
    await db.delete(pinned)
    await db.commit()


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

    member_count: int | None = None
    mentions = 0
    if chat.type == ChatType.group:
        member_count = await count_members(db, chat.id)
        mentions = await count_unread_mentions(
            db, chat.id, viewer.id, viewer.username, member.last_read_message_id
        )

    return ChatOut(
        chat_public_id=chat.public_id,
        type=chat.type.value,
        title=title,
        description=chat.description if chat.type == ChatType.group else None,
        avatar_url=avatar_url,
        is_pinned=member.is_pinned,
        is_archived=member.is_archived,
        muted_until=member.muted_until,
        unread_count=unread,
        mentions_count=mentions,
        member_count=member_count,
        my_role=member.role.value if chat.type == ChatType.group else None,
        last_message=last_message_out,
        peer_public_id=peer_public_id,
        peer_username=peer_username,
        peer_online=False,
        peer_last_seen_at=peer_last_seen_at,
    )
