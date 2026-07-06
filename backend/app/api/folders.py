"""Папки чатов (Фаза 6): пользовательские вкладки-фильтры поверх списка чатов."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.api.schemas import FolderOut
from app.core.deps import get_current_user
from app.db.models import Chat, ChatMember, Folder, FolderChat, User
from app.db.session import get_db

router = APIRouter(prefix="/folders", tags=["folders"])

_FOLDER_NOT_FOUND = {"code": "folder_not_found", "message": "Папка не найдена"}
_NAME_REQUIRED = {"code": "name_required", "message": "Укажите название папки"}


class FolderCreateBody(BaseModel):
    name: str
    chat_public_ids: list[str] = []


class FolderPatchBody(BaseModel):
    name: str | None = None
    chat_public_ids: list[str] | None = None


async def _resolve_member_chat_ids(
    db: AsyncSession, user_id: int, chat_public_ids: list[str]
) -> list[int]:
    if not chat_public_ids:
        return []
    result = await db.execute(
        select(Chat.public_id, Chat.id)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .where(
            Chat.public_id.in_(chat_public_ids),
            ChatMember.user_id == user_id,
            ChatMember.left_at.is_(None),
        )
    )
    id_by_public_id: dict[str, int] = {}
    for public_id, chat_id in result.all():
        id_by_public_id[public_id] = chat_id
    missing = [pid for pid in chat_public_ids if pid not in id_by_public_id]
    if missing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "chat_not_found", "message": "Чат не найден"},
        )
    return [id_by_public_id[pid] for pid in chat_public_ids]


async def _get_folder_or_404(db: AsyncSession, folder_public_id: str, user_id: int) -> Folder:
    result = await db.execute(
        select(Folder).where(Folder.public_id == folder_public_id, Folder.user_id == user_id)
    )
    folder = result.scalar_one_or_none()
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_FOLDER_NOT_FOUND)
    return folder


async def _build_folder_out(db: AsyncSession, folder: Folder) -> FolderOut:
    result = await db.execute(
        select(Chat.public_id)
        .join(FolderChat, FolderChat.chat_id == Chat.id)
        .where(FolderChat.folder_id == folder.id)
    )
    return FolderOut(
        folder_public_id=folder.public_id,
        name=folder.name,
        position=folder.position,
        chat_public_ids=list(result.scalars()),
    )


@router.get("", response_model=list[FolderOut])
async def list_folders(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[FolderOut]:
    result = await db.execute(
        select(Folder).where(Folder.user_id == user.id).order_by(Folder.position, Folder.id)
    )
    return [await _build_folder_out(db, folder) for folder in result.scalars()]


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
async def create_folder(
    body: FolderCreateBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FolderOut:
    name = body.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=_NAME_REQUIRED)
    chat_ids = await _resolve_member_chat_ids(db, user.id, body.chat_public_ids)

    max_position_result = await db.execute(
        select(func.max(Folder.position)).where(Folder.user_id == user.id)
    )
    next_position = (max_position_result.scalar_one() or 0) + 1

    folder = Folder(
        public_id=str(ULID()),
        user_id=user.id,
        name=name,
        position=next_position,
        created_at=datetime.now(UTC),
    )
    db.add(folder)
    await db.flush()
    for chat_id in chat_ids:
        db.add(FolderChat(folder_id=folder.id, chat_id=chat_id))
    await db.commit()
    return await _build_folder_out(db, folder)


@router.patch("/{folder_public_id}", response_model=FolderOut)
async def update_folder(
    folder_public_id: str,
    body: FolderPatchBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FolderOut:
    folder = await _get_folder_or_404(db, folder_public_id, user.id)

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=_NAME_REQUIRED)
        folder.name = name

    if body.chat_public_ids is not None:
        chat_ids = await _resolve_member_chat_ids(db, user.id, body.chat_public_ids)
        await db.execute(delete(FolderChat).where(FolderChat.folder_id == folder.id))
        for chat_id in chat_ids:
            db.add(FolderChat(folder_id=folder.id, chat_id=chat_id))

    await db.commit()
    return await _build_folder_out(db, folder)


@router.delete("/{folder_public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    folder = await _get_folder_or_404(db, folder_public_id, user.id)
    await db.delete(folder)
    await db.commit()
