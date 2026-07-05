"""История и отправка сообщений в личном чате."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.api.schemas import MessageOut
from app.core.deps import get_current_user
from app.db.models import (
    File,
    FileKind,
    Message,
    MessageAttachment,
    MessageHidden,
    MessageReaction,
    MessageType,
    User,
)
from app.db.session import get_db
from app.services.chat import build_message_out, get_membership_or_404
from app.ws.events import broadcast_to_chat

_FILE_KIND_TO_MESSAGE_TYPE: dict[FileKind, MessageType] = {
    FileKind.image: MessageType.photo,
    FileKind.video: MessageType.video,
    FileKind.audio: MessageType.audio,
    FileKind.voice: MessageType.voice,
    FileKind.document: MessageType.document,
}

router = APIRouter(prefix="/chats/{chat_public_id}/messages", tags=["messages"])

_EDIT_DELETE_ALL_WINDOW = timedelta(hours=48)

_MESSAGE_NOT_FOUND = HTTPException(
    status.HTTP_404_NOT_FOUND,
    detail={"code": "message_not_found", "message": "Сообщение не найдено"},
)


class SendMessageBody(BaseModel):
    client_msg_id: uuid.UUID
    body: str | None = Field(default=None, max_length=8000)
    reply_to_public_id: str | None = None
    file_public_ids: list[str] = Field(default_factory=list, max_length=10)


class EditMessageBody(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class ReactionBody(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)


async def _get_message_or_404(db: AsyncSession, chat_id: int, message_public_id: str) -> Message:
    result = await db.execute(
        select(Message).where(Message.public_id == message_public_id, Message.chat_id == chat_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise _MESSAGE_NOT_FOUND
    return message


@router.get("", response_model=list[MessageOut])
async def list_messages(
    chat_public_id: str,
    before: str | None = Query(default=None),
    limit: int = Query(default=50, le=100, ge=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)

    stmt = select(Message).where(Message.chat_id == chat.id)
    if before:
        before_result = await db.execute(
            select(Message.id).where(Message.public_id == before, Message.chat_id == chat.id)
        )
        before_id = before_result.scalar_one_or_none()
        if before_id is not None:
            stmt = stmt.where(Message.id < before_id)
    stmt = stmt.order_by(Message.id.desc()).limit(limit)

    result = await db.execute(stmt)
    messages = list(reversed(result.scalars().all()))

    hidden_result = await db.execute(
        select(MessageHidden.message_id).where(MessageHidden.user_id == user.id)
    )
    hidden_ids = set(hidden_result.scalars().all())

    return [
        await build_message_out(db, message, chat, user.id)
        for message in messages
        if message.id not in hidden_ids
    ]


@router.post("", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def send_message(
    chat_public_id: str,
    body: SendMessageBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)

    if not (body.body and body.body.strip()) and not body.file_public_ids:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_message", "message": "Сообщение не может быть пустым"},
        )

    reply_to_id = None
    if body.reply_to_public_id:
        reply_result = await db.execute(
            select(Message.id).where(
                Message.public_id == body.reply_to_public_id, Message.chat_id == chat.id
            )
        )
        reply_to_id = reply_result.scalar_one_or_none()
        if reply_to_id is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"code": "reply_not_found", "message": "Цитируемое сообщение не найдено"},
            )

    attachment_files: list[File] = []
    if body.file_public_ids:
        files_result = await db.execute(
            select(File).where(File.public_id.in_(body.file_public_ids), File.owner_id == user.id)
        )
        by_public_id = {f.public_id: f for f in files_result.scalars().all()}
        missing = [fid for fid in body.file_public_ids if fid not in by_public_id]
        if missing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"code": "file_not_found", "message": "Вложение не найдено"},
            )
        attachment_files = [by_public_id[fid] for fid in body.file_public_ids]

    if len(attachment_files) > 1:
        message_type = MessageType.album
    elif attachment_files:
        message_type = _FILE_KIND_TO_MESSAGE_TYPE[attachment_files[0].kind]
    else:
        message_type = MessageType.text

    now = datetime.now(UTC)
    insert_stmt = (
        pg_insert(Message)
        .values(
            public_id=str(ULID()),
            chat_id=chat.id,
            sender_id=user.id,
            client_msg_id=body.client_msg_id,
            type=message_type,
            body=body.body,
            reply_to_id=reply_to_id,
            created_at=now,
        )
        .on_conflict_do_nothing(index_elements=["chat_id", "sender_id", "client_msg_id"])
        .returning(Message.id)
    )
    result = await db.execute(insert_stmt)
    message_id = result.scalar_one_or_none()

    if message_id is None:
        existing_result = await db.execute(
            select(Message).where(
                Message.chat_id == chat.id,
                Message.sender_id == user.id,
                Message.client_msg_id == body.client_msg_id,
            )
        )
        message = existing_result.scalar_one()
        await db.commit()
    else:
        for position, attachment_file in enumerate(attachment_files):
            db.add(
                MessageAttachment(
                    message_id=message_id, file_id=attachment_file.id, position=position
                )
            )
        chat.updated_at = now
        await db.commit()
        message_result = await db.execute(select(Message).where(Message.id == message_id))
        message = message_result.scalar_one()

    out = await build_message_out(db, message, chat, user.id)
    if message_id is not None:
        await broadcast_to_chat(db, chat.id, "message.new", out.model_dump(mode="json"))
    return out


@router.patch("/{message_public_id}", response_model=MessageOut)
async def edit_message(
    chat_public_id: str,
    message_public_id: str,
    body: EditMessageBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)
    message = await _get_message_or_404(db, chat.id, message_public_id)

    if message.sender_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "not_owner", "message": "Можно редактировать только свои сообщения"},
        )
    if message.deleted_for_all_at is not None:
        raise _MESSAGE_NOT_FOUND

    message.body = body.body
    message.edited_at = datetime.now(UTC)
    await db.commit()

    out = await build_message_out(db, message, chat, user.id)
    await broadcast_to_chat(db, chat.id, "message.edited", out.model_dump(mode="json"))
    return out


@router.delete("/{message_public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    chat_public_id: str,
    message_public_id: str,
    scope: Literal["self", "all"] = Query(default="self"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)
    message = await _get_message_or_404(db, chat.id, message_public_id)

    if scope == "self":
        stmt = (
            pg_insert(MessageHidden)
            .values(message_id=message.id, user_id=user.id)
            .on_conflict_do_nothing(index_elements=["message_id", "user_id"])
        )
        await db.execute(stmt)
        await db.commit()
        return

    if message.sender_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "not_owner", "message": "Можно удалить у всех только своё сообщение"},
        )
    if message.deleted_for_all_at is not None:
        return
    if datetime.now(UTC) - message.created_at > _EDIT_DELETE_ALL_WINDOW:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "delete_window_expired", "message": "Прошло больше 48 часов"},
        )

    message.deleted_for_all_at = datetime.now(UTC)
    await db.commit()
    await broadcast_to_chat(
        db, chat.id, "message.deleted", {"message_public_id": message.public_id, "scope": "all"}
    )


@router.post("/{message_public_id}/reactions", response_model=MessageOut)
async def toggle_reaction(
    chat_public_id: str,
    message_public_id: str,
    body: ReactionBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)
    message = await _get_message_or_404(db, chat.id, message_public_id)

    existing_result = await db.execute(
        select(MessageReaction).where(
            MessageReaction.message_id == message.id, MessageReaction.user_id == user.id
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing is not None and existing.emoji == body.emoji:
        await db.delete(existing)
    else:
        stmt = (
            pg_insert(MessageReaction)
            .values(
                message_id=message.id,
                user_id=user.id,
                emoji=body.emoji,
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_update(
                index_elements=["message_id", "user_id"], set_={"emoji": body.emoji}
            )
        )
        await db.execute(stmt)

    await db.commit()
    out = await build_message_out(db, message, chat, user.id)
    await broadcast_to_chat(db, chat.id, "reaction.updated", out.model_dump(mode="json"))
    return out
