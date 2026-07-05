"""SQLAlchemy-модели. Должны соответствовать db/schema.sql (см. ADR-004 в docs/DECISIONS.md).

Пока моделируются только таблицы, необходимые для реализованных фаз (0-3):
users, files, email_login_codes, sessions, contacts, blocked_users, chats,
chat_members, messages, message_reactions, message_hidden, message_attachments,
message_bookmarks, pinned_messages, drafts.
Остальные таблицы схемы (опросы, инвайты и т.д.) получат модели по мере
реализации следующих фаз.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ThemePref(enum.StrEnum):
    system = "system"
    light = "light"
    dark = "dark"


class PrivacyLevel(enum.StrEnum):
    all = "all"
    contacts = "contacts"
    nobody = "nobody"


class FileKind(enum.StrEnum):
    image = "image"
    video = "video"
    audio = "audio"
    voice = "voice"
    document = "document"
    avatar = "avatar"
    sticker = "sticker"


class ChatType(enum.StrEnum):
    direct = "direct"
    group = "group"
    saved = "saved"


class MemberRole(enum.StrEnum):
    owner = "owner"
    admin = "admin"
    member = "member"


class MessageType(enum.StrEnum):
    text = "text"
    photo = "photo"
    video = "video"
    audio = "audio"
    voice = "voice"
    document = "document"
    contact = "contact"
    location = "location"
    album = "album"
    poll = "poll"
    system = "system"


# create_type=False: типы создаются миграцией (raw SQL db/schema.sql), не моделями.
theme_pref_pg = PgEnum(ThemePref, name="theme_pref", create_type=False)
privacy_level_pg = PgEnum(PrivacyLevel, name="privacy_level", create_type=False)
file_kind_pg = PgEnum(FileKind, name="file_kind", create_type=False)
chat_type_pg = PgEnum(ChatType, name="chat_type", create_type=False)
member_role_pg = PgEnum(MemberRole, name="member_role", create_type=False)
message_type_pg = PgEnum(MessageType, name="message_type", create_type=False)


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(CHAR(26), unique=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[FileKind] = mapped_column(file_kind_pg, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column()
    height: Mapped[int | None] = mapped_column()
    duration_ms: Mapped[int | None] = mapped_column()
    waveform: Mapped[list[float] | None] = mapped_column(JSONB)
    thumb_key: Mapped[str | None] = mapped_column(String(512))
    original_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(CHAR(26), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    username: Mapped[str | None] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    bio: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    avatar_file_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("files.id", ondelete="SET NULL")
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))
    theme: Mapped[ThemePref] = mapped_column(
        theme_pref_pg, nullable=False, default=ThemePref.system
    )
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="ru")
    privacy_last_seen: Mapped[PrivacyLevel] = mapped_column(
        privacy_level_pg, nullable=False, default=PrivacyLevel.all
    )
    privacy_avatar: Mapped[PrivacyLevel] = mapped_column(
        privacy_level_pg, nullable=False, default=PrivacyLevel.all
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    avatar_file: Mapped[File | None] = relationship(foreign_keys=[avatar_file_id])


class EmailLoginCode(Base):
    __tablename__ = "email_login_codes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    device_label: Mapped[str | None] = mapped_column(String(128))
    ip: Mapped[str | None] = mapped_column(String(45))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("owner_id", "contact_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    contact_user: Mapped[User] = relationship(foreign_keys=[contact_id])


class BlockedUser(Base):
    __tablename__ = "blocked_users"

    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    blocked_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    blocked_user: Mapped[User] = relationship(foreign_keys=[blocked_id])


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(CHAR(26), unique=True, nullable=False)
    type: Mapped[ChatType] = mapped_column(chat_type_pg, nullable=False)
    title: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(512))
    avatar_file_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("files.id", ondelete="SET NULL")
    )
    owner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChatMember(Base):
    __tablename__ = "chat_members"
    __table_args__ = (UniqueConstraint("chat_id", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MemberRole] = mapped_column(
        member_role_pg, nullable=False, default=MemberRole.member
    )
    can_delete_messages: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_ban: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_invite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_pin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_edit_info: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    muted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_read_message_id: Mapped[int | None] = mapped_column(BigInteger)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("chat_id", "sender_id", "client_msg_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(CHAR(26), unique=True, nullable=False)
    chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    client_msg_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    type: Mapped[MessageType] = mapped_column(
        message_type_pg, nullable=False, default=MessageType.text
    )
    body: Mapped[str | None] = mapped_column(Text)
    reply_to_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="SET NULL")
    )
    forwarded_from_msg_id: Mapped[int | None] = mapped_column(BigInteger)
    forwarded_from_user_id: Mapped[int | None] = mapped_column(BigInteger)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_for_all_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # generated ALWAYS AS (to_tsvector('russian', ...)) STORED — заполняется Postgres'ом,
    # приложение никогда в неё не пишет.
    search_tsv: Mapped[str | None] = mapped_column(TSVECTOR)

    sender: Mapped[User | None] = relationship(foreign_keys=[sender_id])
    reply_to: Mapped[Message | None] = relationship(remote_side=[id])


class MessageReaction(Base):
    __tablename__ = "message_reactions"

    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    emoji: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("files.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    file: Mapped[File] = relationship()


class MessageBookmark(Base):
    __tablename__ = "message_bookmarks"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MessageHidden(Base):
    __tablename__ = "message_hidden"

    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )


class PinnedMessage(Base):
    __tablename__ = "pinned_messages"

    chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True
    )
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    pinned_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    pinned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Draft(Base):
    __tablename__ = "drafts"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    reply_to_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
