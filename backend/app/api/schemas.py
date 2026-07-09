"""Общие Pydantic-схемы ответов API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.db.models import File, FileKind, MessageType, PrivacyLevel, ThemePref, User


class ReactionSummary(BaseModel):
    emoji: str
    count: int
    reacted_by_me: bool


class FileOut(BaseModel):
    public_id: str
    kind: FileKind
    url: str
    thumb_url: str | None
    mime_type: str
    size_bytes: int
    width: int | None
    height: int | None
    duration_ms: int | None
    waveform: list[float] | None
    original_name: str | None

    @staticmethod
    def from_model(file: File) -> FileOut:
        return FileOut(
            public_id=file.public_id,
            kind=file.kind,
            url=f"/media/{file.storage_key}",
            thumb_url=f"/media/{file.thumb_key}" if file.thumb_key else None,
            mime_type=file.mime_type,
            size_bytes=file.size_bytes,
            width=file.width,
            height=file.height,
            duration_ms=file.duration_ms,
            waveform=file.waveform,
            original_name=file.original_name,
        )


class PollOptionOut(BaseModel):
    position: int
    text: str
    votes: int
    voted_by_me: bool


class PollOut(BaseModel):
    question: str
    is_anonymous: bool
    multi_choice: bool
    closed_at: datetime | None
    total_votes: int
    options: list[PollOptionOut]


class MessageOut(BaseModel):
    message_public_id: str
    chat_public_id: str
    sender_public_id: str | None
    type: MessageType
    body: str | None
    payload: dict[str, object] | None
    poll: PollOut | None
    reply_to_public_id: str | None
    forwarded_from_user_public_id: str | None
    edited_at: datetime | None
    deleted_for_all: bool
    created_at: datetime
    status: str
    reactions: list[ReactionSummary]
    attachments: list[FileOut]
    bookmarked: bool
    scheduled_at: datetime | None


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
    e2ee_public_key: str | None

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
            e2ee_public_key=user.e2ee_public_key,
        )


class ChatMemberOut(BaseModel):
    user_public_id: str
    username: str | None
    display_name: str
    avatar_url: str | None
    role: str
    can_delete_messages: bool
    can_ban: bool
    can_invite: bool
    can_pin: bool
    can_edit_info: bool
    online: bool
    last_seen_at: datetime | None


class ChatInviteOut(BaseModel):
    token: str
    chat_public_id: str
    max_uses: int | None
    used_count: int
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class InvitePreviewOut(BaseModel):
    chat_title: str
    chat_description: str | None
    member_count: int
    avatar_url: str | None
    valid: bool


class ChatOut(BaseModel):
    chat_public_id: str
    type: str
    title: str
    description: str | None
    avatar_url: str | None
    is_pinned: bool
    is_archived: bool
    muted_until: datetime | None
    unread_count: int
    mentions_count: int
    member_count: int | None
    my_role: str | None
    last_message: MessageOut | None
    peer_public_id: str | None
    peer_username: str | None
    peer_online: bool
    peer_last_seen_at: datetime | None
    is_secret: bool
    peer_e2ee_public_key: str | None


class FolderOut(BaseModel):
    folder_public_id: str
    name: str
    position: int
    chat_public_ids: list[str]


class SessionOut(BaseModel):
    id: int
    device_label: str | None
    ip: str | None
    created_at: datetime
    last_used_at: datetime
    is_current: bool
