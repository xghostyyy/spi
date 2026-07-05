"""Загрузка медиафайлов для сообщений: фото, видео, аудио, документы, голосовые."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.api.schemas import FileOut
from app.core.deps import get_current_user
from app.db.models import File, FileKind, User
from app.db.session import get_db
from app.services.media import InvalidMediaError, process_image
from app.services.storage import get_storage

router = APIRouter(prefix="/files", tags=["files"])

_ALLOWED_MIME_BY_KIND: dict[FileKind, set[str]] = {
    FileKind.image: {"image/png", "image/jpeg", "image/webp", "image/gif"},
    FileKind.video: {"video/mp4", "video/webm", "video/quicktime"},
    FileKind.audio: {"audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg", "audio/webm"},
    FileKind.voice: {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav"},
    FileKind.document: set(),  # любой MIME — ограничение только по размеру
}

_MAX_SIZE_BY_KIND: dict[FileKind, int] = {
    FileKind.image: 15 * 1024 * 1024,
    FileKind.video: 100 * 1024 * 1024,
    FileKind.audio: 25 * 1024 * 1024,
    FileKind.voice: 15 * 1024 * 1024,
    FileKind.document: 50 * 1024 * 1024,
}

_EXT_BY_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mov",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/wav": "wav",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
}


@router.post("", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    kind: FileKind = Form(...),
    duration_ms: int | None = Form(default=None),
    waveform: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileOut:
    valid_kinds = (
        FileKind.image,
        FileKind.video,
        FileKind.audio,
        FileKind.voice,
        FileKind.document,
    )
    if kind not in valid_kinds:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_kind", "message": "Недопустимый тип вложения"},
        )

    allowed = _ALLOWED_MIME_BY_KIND[kind]
    if allowed and file.content_type not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_file_type",
                "message": "Недопустимый MIME-тип для этого вложения",
            },
        )

    data = await file.read()
    max_size = _MAX_SIZE_BY_KIND[kind]
    if len(data) > max_size:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "file_too_large",
                "message": f"Файл больше {max_size // (1024 * 1024)} МБ",
            },
        )

    file_public_id = str(ULID())
    width = height = None
    thumb_key: str | None = None
    mime_type = file.content_type or "application/octet-stream"
    storage = get_storage()

    if kind == FileKind.image:
        try:
            processed, thumb_bytes, width, height = await process_image(data)
        except InvalidMediaError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "invalid_image", "message": str(exc)},
            ) from exc
        mime_type = "image/jpeg"
        storage_key = f"media/{file_public_id}.jpg"
        thumb_key = f"media/{file_public_id}_thumb.jpg"
        await storage.save(storage_key, processed)
        await storage.save(thumb_key, thumb_bytes)
        size_bytes = len(processed)
    else:
        original_ext = (file.filename or "").rsplit(".", 1)[-1].lower() if file.filename else ""
        ext = _EXT_BY_MIME.get(mime_type) or (original_ext if original_ext.isalnum() else "bin")
        storage_key = f"media/{file_public_id}.{ext}"
        await storage.save(storage_key, data)
        size_bytes = len(data)

    parsed_waveform: list[float] | None = None
    if kind == FileKind.voice and waveform:
        try:
            parsed_waveform = [float(v) for v in json.loads(waveform)]
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "invalid_waveform",
                    "message": "waveform должен быть JSON-массивом чисел",
                },
            ) from exc

    file_row = File(
        public_id=file_public_id,
        owner_id=user.id,
        kind=kind,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=size_bytes,
        width=width,
        height=height,
        duration_ms=duration_ms,
        waveform=parsed_waveform,
        thumb_key=thumb_key,
        original_name=file.filename[:255] if file.filename else None,
        created_at=datetime.now(UTC),
    )
    db.add(file_row)
    await db.commit()

    return FileOut.from_model(file_row)
