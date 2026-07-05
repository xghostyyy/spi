"""Профиль текущего пользователя: чтение, редактирование, username, аватар."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.api.schemas import UserOut
from app.core.deps import get_current_user
from app.db.models import File, FileKind, PrivacyLevel, ThemePref, User
from app.db.session import get_db
from app.services.avatar import (
    ALLOWED_MIME_TYPES,
    AVATAR_SIZE,
    MAX_UPLOAD_BYTES,
    InvalidImageError,
    process_avatar,
)
from app.services.storage import get_storage

router = APIRouter(prefix="/users", tags=["users"])

_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,31}$")


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    bio: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, min_length=3, max_length=32)
    theme: ThemePref | None = None
    locale: str | None = Field(default=None, min_length=2, max_length=8)
    privacy_last_seen: PrivacyLevel | None = None
    privacy_avatar: PrivacyLevel | None = None


async def _load_avatar(db: AsyncSession, user: User) -> File | None:
    if not user.avatar_file_id:
        return None
    result = await db.execute(select(File).where(File.id == user.avatar_file_id))
    return result.scalar_one_or_none()


@router.get("/me", response_model=UserOut)
async def get_me(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> UserOut:
    avatar_file = await _load_avatar(db, user)
    return UserOut.from_model(user, avatar_file)


@router.patch("/me", response_model=UserOut)
async def update_me(
    patch: ProfilePatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    if patch.username is not None and patch.username != user.username:
        username = patch.username.strip()
        if not _USERNAME_RE.match(username):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "invalid_username",
                    "message": "Username: латиница/цифры/_, начинается с буквы, 3-32 символа",
                },
            )
        existing = await db.execute(select(User.id).where(User.username == username))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"code": "username_taken", "message": "Этот username уже занят"},
            )
        user.username = username

    if patch.display_name is not None:
        user.display_name = patch.display_name.strip()
    if patch.bio is not None:
        user.bio = patch.bio.strip() or None
    if patch.theme is not None:
        user.theme = patch.theme
    if patch.locale is not None:
        user.locale = patch.locale
    if patch.privacy_last_seen is not None:
        user.privacy_last_seen = patch.privacy_last_seen
    if patch.privacy_avatar is not None:
        user.privacy_avatar = patch.privacy_avatar

    await db.commit()
    await db.refresh(user)

    avatar_file = await _load_avatar(db, user)
    return UserOut.from_model(user, avatar_file)


@router.get("/check-username")
async def check_username(
    username: str = Query(..., min_length=1, max_length=32),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    username = username.strip()
    if not _USERNAME_RE.match(username):
        return {"available": False}
    if username == user.username:
        return {"available": True}
    result = await db.execute(select(User.id).where(User.username == username))
    return {"available": result.scalar_one_or_none() is None}


@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_file_type", "message": "Разрешены только PNG/JPEG/WEBP"},
        )
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "file_too_large", "message": "Файл больше 5 МБ"},
        )

    try:
        processed = await process_avatar(data)
    except InvalidImageError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_image", "message": str(exc)},
        ) from exc

    file_public_id = str(ULID())
    storage_key = f"avatars/{file_public_id}.jpg"
    storage = get_storage()
    await storage.save(storage_key, processed)

    now = datetime.now(UTC)
    avatar_row = File(
        public_id=file_public_id,
        owner_id=user.id,
        kind=FileKind.avatar,
        storage_key=storage_key,
        mime_type="image/jpeg",
        size_bytes=len(processed),
        width=AVATAR_SIZE,
        height=AVATAR_SIZE,
        created_at=now,
    )
    db.add(avatar_row)
    await db.flush()

    user.avatar_file_id = avatar_row.id
    await db.commit()

    return UserOut.from_model(user, avatar_row)
