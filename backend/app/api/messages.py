"""История и отправка сообщений в личном чате."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.api.schemas import MessageOut
from app.core.deps import get_current_user
from app.db.models import (
    Chat,
    ChatMember,
    File,
    FileKind,
    MemberRole,
    Message,
    MessageAttachment,
    MessageHidden,
    MessageReaction,
    MessageType,
    Poll,
    PollOption,
    PollVote,
    User,
)
from app.db.session import get_db
from app.services.chat import build_message_out, get_membership_or_404
from app.services.push import notify_message_sent
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

_SECRET_CHAT_TEXT_ONLY = HTTPException(
    status.HTTP_400_BAD_REQUEST,
    detail={
        "code": "secret_chat_text_only",
        "message": "В секретном чате поддерживаются только зашифрованные текстовые сообщения",
    },
)

_ENCRYPTED_NOT_ALLOWED = HTTPException(
    status.HTTP_400_BAD_REQUEST,
    detail={
        "code": "encrypted_not_allowed",
        "message": "Шифрование доступно только в секретных чатах",
    },
)

_CHANNEL_READ_ONLY = HTTPException(
    status.HTTP_403_FORBIDDEN,
    detail={
        "code": "channel_read_only",
        "message": "Публиковать в канале могут только владелец и администраторы",
    },
)


class ContactPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    phone: str = Field(min_length=1, max_length=32)


class LocationPayload(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class PollPayload(BaseModel):
    question: str = Field(min_length=1, max_length=255)
    options: list[str] = Field(min_length=2, max_length=10)
    is_anonymous: bool = True
    multi_choice: bool = False


class StickerPayload(BaseModel):
    pack: str = Field(min_length=1, max_length=64)
    sticker_id: str = Field(min_length=1, max_length=64)
    emoji: str = Field(min_length=1, max_length=8)
    url: str = Field(min_length=1, max_length=1024)


class GifPayload(BaseModel):
    url: str = Field(min_length=1, max_length=1024)
    preview_url: str | None = Field(default=None, max_length=1024)
    width: int | None = None
    height: int | None = None


class CallPayload(BaseModel):
    kind: Literal["audio", "video"]
    outcome: Literal["answered", "missed", "declined", "canceled"]
    duration_seconds: int | None = Field(default=None, ge=0)


class EncryptedPayload(BaseModel):
    ciphertext: str = Field(min_length=1, max_length=16000)
    iv: str = Field(min_length=1, max_length=64)


class SendMessageBody(BaseModel):
    client_msg_id: uuid.UUID
    body: str | None = Field(default=None, max_length=8000)
    reply_to_public_id: str | None = None
    file_public_ids: list[str] = Field(default_factory=list, max_length=10)
    forward_from_message_public_id: str | None = None
    contact: ContactPayload | None = None
    location: LocationPayload | None = None
    poll: PollPayload | None = None
    sticker: StickerPayload | None = None
    gif: GifPayload | None = None
    call: CallPayload | None = None
    encrypted: EncryptedPayload | None = None
    scheduled_at: datetime | None = None
    is_video_note: bool = False


class PollVoteBody(BaseModel):
    option_positions: list[int] = Field(min_length=1, max_length=10)


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
    q: str | None = Query(default=None, min_length=1, max_length=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)

    stmt = select(Message).where(
        Message.chat_id == chat.id,
        (Message.scheduled_at.is_(None)) | (Message.scheduled_broadcast_at.is_not(None)),
    )
    if before:
        before_result = await db.execute(
            select(Message.id).where(Message.public_id == before, Message.chat_id == chat.id)
        )
        before_id = before_result.scalar_one_or_none()
        if before_id is not None:
            stmt = stmt.where(Message.id < before_id)
    if q:
        stmt = stmt.where(Message.search_tsv.op("@@")(func.plainto_tsquery("russian", q)))
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
    chat, member = await get_membership_or_404(db, chat_public_id, user)

    if chat.is_channel and member.role == MemberRole.member:
        raise _CHANNEL_READ_ONLY

    if chat.is_secret:
        if body.encrypted is None or any(
            [
                body.body,
                body.file_public_ids,
                body.forward_from_message_public_id,
                body.contact,
                body.location,
                body.poll,
                body.sticker,
                body.gif,
                body.call,
            ]
        ):
            raise _SECRET_CHAT_TEXT_ONLY
    elif body.encrypted is not None:
        raise _ENCRYPTED_NOT_ALLOWED

    if body.scheduled_at is not None and body.scheduled_at <= datetime.now(UTC):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "scheduled_at_in_past",
                "message": "Время отправки должно быть в будущем",
            },
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

    forwarded_from_msg_id: int | None = None
    forwarded_from_user_id: int | None = None
    payload: dict[str, object] | None = None
    attachments_to_link: list[tuple[int, int]] = []
    poll_to_create: PollPayload | None = None
    message_type: MessageType

    if body.forward_from_message_public_id:
        source_result = await db.execute(
            select(Message).where(Message.public_id == body.forward_from_message_public_id)
        )
        source = source_result.scalar_one_or_none()
        if source is None or source.deleted_for_all_at is not None:
            raise _MESSAGE_NOT_FOUND
        if source.type == MessageType.poll:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "cannot_forward_poll", "message": "Опрос нельзя переслать"},
            )
        source_member_result = await db.execute(
            select(ChatMember).where(
                ChatMember.chat_id == source.chat_id,
                ChatMember.user_id == user.id,
                ChatMember.left_at.is_(None),
            )
        )
        if source_member_result.scalar_one_or_none() is None:
            raise _MESSAGE_NOT_FOUND
        source_chat_result = await db.execute(
            select(Chat.is_secret).where(Chat.id == source.chat_id)
        )
        if source_chat_result.scalar_one():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "cannot_forward_secret",
                    "message": "Сообщения из секретных чатов нельзя пересылать",
                },
            )

        message_type = source.type
        final_body = source.body
        payload = source.payload
        forwarded_from_msg_id = source.id
        forwarded_from_user_id = source.sender_id
        source_attachments_result = await db.execute(
            select(MessageAttachment.file_id, MessageAttachment.position)
            .where(MessageAttachment.message_id == source.id)
            .order_by(MessageAttachment.position)
        )
        attachments_to_link = [tuple(row) for row in source_attachments_result.all()]
    elif body.encrypted is not None:
        message_type = MessageType.text
        final_body = None
        payload = body.encrypted.model_dump()
    elif body.contact is not None:
        message_type = MessageType.contact
        final_body = None
        payload = body.contact.model_dump()
    elif body.location is not None:
        message_type = MessageType.location
        final_body = None
        payload = body.location.model_dump()
    elif body.sticker is not None:
        message_type = MessageType.sticker
        final_body = None
        payload = body.sticker.model_dump()
    elif body.gif is not None:
        message_type = MessageType.gif
        final_body = None
        payload = body.gif.model_dump()
    elif body.call is not None:
        message_type = MessageType.call
        final_body = None
        payload = body.call.model_dump()
    elif body.poll is not None:
        message_type = MessageType.poll
        final_body = None
        poll_to_create = body.poll
    else:
        if not (body.body and body.body.strip()) and not body.file_public_ids:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "empty_message", "message": "Сообщение не может быть пустым"},
            )
        final_body = body.body

        attachment_files: list[File] = []
        if body.file_public_ids:
            files_result = await db.execute(
                select(File).where(
                    File.public_id.in_(body.file_public_ids), File.owner_id == user.id
                )
            )
            by_public_id = {f.public_id: f for f in files_result.scalars().all()}
            missing = [fid for fid in body.file_public_ids if fid not in by_public_id]
            if missing:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail={"code": "file_not_found", "message": "Вложение не найдено"},
                )
            attachment_files = [by_public_id[fid] for fid in body.file_public_ids]
        attachments_to_link = [(f.id, i) for i, f in enumerate(attachment_files)]

        if (
            body.is_video_note
            and len(attachment_files) == 1
            and attachment_files[0].kind == FileKind.video
        ):
            message_type = MessageType.video_note
        elif len(attachment_files) > 1:
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
            body=final_body,
            reply_to_id=reply_to_id,
            forwarded_from_msg_id=forwarded_from_msg_id,
            forwarded_from_user_id=forwarded_from_user_id,
            payload=payload,
            created_at=now,
            scheduled_at=body.scheduled_at,
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
        for file_id, position in attachments_to_link:
            db.add(MessageAttachment(message_id=message_id, file_id=file_id, position=position))
        if poll_to_create is not None:
            db.add(
                Poll(
                    message_id=message_id,
                    question=poll_to_create.question,
                    is_anonymous=poll_to_create.is_anonymous,
                    multi_choice=poll_to_create.multi_choice,
                )
            )
            for position, text in enumerate(poll_to_create.options):
                db.add(PollOption(poll_id=message_id, text=text, position=position))
        if body.scheduled_at is None:
            chat.updated_at = now
        await db.commit()
        message_result = await db.execute(select(Message).where(Message.id == message_id))
        message = message_result.scalar_one()

    out = await build_message_out(db, message, chat, user.id)
    if message_id is not None and message.scheduled_at is None:
        await broadcast_to_chat(db, chat.id, "message.new", out.model_dump(mode="json"))
        await notify_message_sent(db, chat, message, user)
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

    if chat.is_secret:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "secret_chat_no_edit",
                "message": "Редактирование сообщений в секретных чатах не поддерживается",
            },
        )
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


_POLL_NOT_FOUND = HTTPException(
    status.HTTP_404_NOT_FOUND, detail={"code": "poll_not_found", "message": "Опрос не найден"}
)
_POLL_CLOSED = HTTPException(
    status.HTTP_400_BAD_REQUEST, detail={"code": "poll_closed", "message": "Опрос уже закрыт"}
)


async def _get_poll_or_404(db: AsyncSession, message: Message) -> Poll:
    if message.type != MessageType.poll:
        raise _POLL_NOT_FOUND
    poll_result = await db.execute(select(Poll).where(Poll.message_id == message.id))
    poll = poll_result.scalar_one_or_none()
    if poll is None:
        raise _POLL_NOT_FOUND
    return poll


@router.post("/{message_public_id}/poll/vote", response_model=MessageOut)
async def vote_poll(
    chat_public_id: str,
    message_public_id: str,
    body: PollVoteBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)
    message = await _get_message_or_404(db, chat.id, message_public_id)
    poll = await _get_poll_or_404(db, message)
    if poll.closed_at is not None:
        raise _POLL_CLOSED

    options_result = await db.execute(
        select(PollOption).where(PollOption.poll_id == poll.message_id)
    )
    options_by_position = {o.position: o for o in options_result.scalars().all()}

    positions = set(body.option_positions)
    if not poll.multi_choice and len(positions) != 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "single_choice_only",
                "message": "В этом опросе можно выбрать только один вариант",
            },
        )
    if not positions.issubset(options_by_position.keys()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_option", "message": "Недопустимый вариант ответа"},
        )

    all_option_ids = [o.id for o in options_by_position.values()]
    await db.execute(
        delete(PollVote).where(PollVote.option_id.in_(all_option_ids), PollVote.user_id == user.id)
    )
    now = datetime.now(UTC)
    for position in positions:
        db.add(
            PollVote(option_id=options_by_position[position].id, user_id=user.id, created_at=now)
        )

    await db.commit()
    out = await build_message_out(db, message, chat, user.id)
    await broadcast_to_chat(db, chat.id, "poll.updated", out.model_dump(mode="json"))
    return out


@router.post("/{message_public_id}/poll/close", response_model=MessageOut)
async def close_poll(
    chat_public_id: str,
    message_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)
    message = await _get_message_or_404(db, chat.id, message_public_id)
    poll = await _get_poll_or_404(db, message)

    if message.sender_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "not_owner", "message": "Закрыть опрос может только его автор"},
        )
    if poll.closed_at is None:
        poll.closed_at = datetime.now(UTC)
        await db.commit()

    out = await build_message_out(db, message, chat, user.id)
    await broadcast_to_chat(db, chat.id, "poll.updated", out.model_dump(mode="json"))
    return out


class RescheduleBody(BaseModel):
    scheduled_at: datetime


def _pending_scheduled_filter(chat_id: int, user_id: int):  # type: ignore[no-untyped-def]
    return (
        Message.chat_id == chat_id,
        Message.sender_id == user_id,
        Message.scheduled_at.is_not(None),
        Message.scheduled_broadcast_at.is_(None),
        Message.deleted_for_all_at.is_(None),
    )


@router.get("/scheduled", response_model=list[MessageOut])
async def list_scheduled_messages(
    chat_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)
    result = await db.execute(
        select(Message)
        .where(*_pending_scheduled_filter(chat.id, user.id))
        .order_by(Message.scheduled_at)
    )
    return [await build_message_out(db, m, chat, user.id) for m in result.scalars()]


@router.patch("/scheduled/{message_public_id}", response_model=MessageOut)
async def reschedule_message(
    chat_public_id: str,
    message_public_id: str,
    body: RescheduleBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)
    if body.scheduled_at <= datetime.now(UTC):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "scheduled_at_in_past",
                "message": "Время отправки должно быть в будущем",
            },
        )
    result = await db.execute(
        select(Message).where(
            Message.public_id == message_public_id, *_pending_scheduled_filter(chat.id, user.id)
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise _MESSAGE_NOT_FOUND

    message.scheduled_at = body.scheduled_at
    await db.commit()
    return await build_message_out(db, message, chat, user.id)


@router.delete("/scheduled/{message_public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_scheduled_message(
    chat_public_id: str,
    message_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)
    result = await db.execute(
        select(Message).where(
            Message.public_id == message_public_id, *_pending_scheduled_filter(chat.id, user.id)
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise _MESSAGE_NOT_FOUND

    await db.delete(message)
    await db.commit()
