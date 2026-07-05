"""Общие Pydantic-схемы ответов API."""

from __future__ import annotations

from pydantic import BaseModel

from app.db.models import File, PrivacyLevel, ThemePref, User


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
