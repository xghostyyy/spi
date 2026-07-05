"""Общие Pydantic-схемы ответов API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.db.models import File, MessageType, PrivacyLevel, ThemePref, User


class ReactionSummary(BaseModel):
    emoji: str
    count: int
    reacted_by_me: bool


class MessageOut(BaseModel):
    message_public_id: str
    chat_public_id: str
    sender_public_id: str | None
    type: MessageType
    body: str | None
    reply_to_public_id: str | None
    edited_at: datetime | None
    deleted_for_all: bool
    created_at: datetime
    status: str
    reactions: list[ReactionSummary]


class UserOut(BaseModel):
    public_id: str
    email: str
    username: str | None
    display_name: str
    bio: str | None
    avatar_url: str | None
    theme: ThemePref
    locale: str
    privacy_last_seen: PrivacyLevel
    privacy_avatar: PrivacyLevel

    @staticmethod
    def from_model(user: User, avatar_file: File | None = None) -> UserOut:
        avatar_url = f"/media/{avatar_file.storage_key}" if avatar_file else None
        return UserOut(
            public_id=user.public_id,
            email=user.email,
            username=user.username,
            display_name=user.display_name,
            bio=user.bio,
            avatar_url=avatar_url,
            theme=user.theme,
            locale=user.locale,
            privacy_last_seen=user.privacy_last_seen,
            privacy_avatar=user.privacy_avatar,
        )


class ChatOut(BaseModel):
    chat_public_id: str
    type: str
    title: str
    avatar_url: str | None
    is_pinned: bool
    is_archived: bool
    muted_until: datetime | None
    unread_count: int
    last_message: MessageOut | None
    peer_public_id: str | None
    peer_username: str | None
    peer_online: bool
    peer_last_seen_at: datetime | None
