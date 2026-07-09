"""Список личных чатов: создание, закреп/архив/mute, медиа-архив, экспорт истории."""

from __future__ import annotations

import html as html_lib
import json
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ChatOut, MessageOut
from app.core.deps import get_current_user
from app.db.models import Chat, ChatMember, Message, MessageType, User
from app.db.session import get_db
from app.services.chat import (
    build_chat_out,
    build_message_out,
    get_membership_or_404,
    get_or_create_direct_chat,
    get_or_create_saved_chat,
    get_or_create_secret_chat,
)

router = APIRouter(prefix="/chats", tags=["chats"])

MediaTab = Literal["media", "files", "voice", "links"]

_TAB_TYPES: dict[str, list[MessageType]] = {
    "media": [MessageType.photo, MessageType.video, MessageType.album],
    "files": [MessageType.document],
    "voice": [MessageType.voice, MessageType.audio],
}


class CreateDirectChatBody(BaseModel):
    username: str


class UpdateChatMembershipBody(BaseModel):
    is_pinned: bool | None = None
    is_archived: bool | None = None
    muted_until: datetime | None = None
    mute_forever: bool | None = None


@router.get("", response_model=list[ChatOut])
async def list_chats(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ChatOut]:
    result = await db.execute(
        select(ChatMember)
        .where(ChatMember.user_id == user.id, ChatMember.left_at.is_(None))
        .order_by(ChatMember.is_pinned.desc())
    )
    memberships = result.scalars().all()

    chats_out = []
    for member in memberships:
        chat_result = await db.execute(select(Chat).where(Chat.id == member.chat_id))
        chat = chat_result.scalar_one()
        chats_out.append(await build_chat_out(db, chat, member, user))

    chats_out.sort(
        key=lambda c: c.last_message.created_at if c.last_message else datetime.min,
        reverse=True,
    )
    chats_out.sort(key=lambda c: c.is_pinned, reverse=True)
    return chats_out


@router.post("", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_direct_chat(
    body: CreateDirectChatBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    username = body.username.strip().lstrip("@")
    if username == user.username:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "self_chat", "message": "Нельзя создать чат с самим собой"},
        )
    target_result = await db.execute(select(User).where(User.username == username))
    target = target_result.scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "Пользователь не найден"},
        )

    chat = await get_or_create_direct_chat(db, user, target)
    await db.commit()

    member_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat.id, ChatMember.user_id == user.id)
    )
    member = member_result.scalar_one()
    return await build_chat_out(db, chat, member, user)


@router.post("/secret", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_secret_chat(
    body: CreateDirectChatBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    """Секретный (E2EE) чат — отдельная сущность от обычного direct-чата с тем же
    собеседником (см. ADR-021). Требует, чтобы у обоих был загружен E2EE-ключ."""
    username = body.username.strip().lstrip("@")
    if username == user.username:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "self_chat", "message": "Нельзя создать чат с самим собой"},
        )
    if user.e2ee_public_key is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "no_e2ee_key", "message": "Сначала настройте свой ключ шифрования"},
        )
    target_result = await db.execute(select(User).where(User.username == username))
    target = target_result.scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "Пользователь не найден"},
        )
    if target.e2ee_public_key is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "peer_no_e2ee_key",
                "message": "У собеседника не настроено шифрование",
            },
        )

    chat = await get_or_create_secret_chat(db, user, target)
    await db.commit()

    member_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat.id, ChatMember.user_id == user.id)
    )
    member = member_result.scalar_one()
    return await build_chat_out(db, chat, member, user)


@router.get("/saved", response_model=ChatOut)
async def get_saved_chat(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ChatOut:
    chat = await get_or_create_saved_chat(db, user)
    await db.commit()

    member_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat.id, ChatMember.user_id == user.id)
    )
    member = member_result.scalar_one()
    return await build_chat_out(db, chat, member, user)


@router.patch("/{chat_public_id}", response_model=ChatOut)
async def update_chat_membership(
    chat_public_id: str,
    body: UpdateChatMembershipBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat, member = await get_membership_or_404(db, chat_public_id, user)

    if body.is_pinned is not None:
        member.is_pinned = body.is_pinned
    if body.is_archived is not None:
        member.is_archived = body.is_archived
    if body.mute_forever:
        member.muted_until = datetime.max.replace(tzinfo=UTC)
    elif body.muted_until is not None:
        member.muted_until = body.muted_until
    elif "muted_until" in body.model_fields_set and body.muted_until is None:
        member.muted_until = None

    await db.commit()
    return await build_chat_out(db, chat, member, user)


@router.get("/{chat_public_id}/media", response_model=list[MessageOut])
async def get_chat_media(
    chat_public_id: str,
    tab: MediaTab = Query(...),
    limit: int = Query(default=100, le=200, ge=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)

    stmt = select(Message).where(Message.chat_id == chat.id, Message.deleted_for_all_at.is_(None))
    if tab == "links":
        stmt = stmt.where(Message.body.op("~")(r"https?://"))
    else:
        stmt = stmt.where(Message.type.in_(_TAB_TYPES[tab]))
    stmt = stmt.order_by(Message.id.desc()).limit(limit)

    result = await db.execute(stmt)
    messages = list(reversed(result.scalars().all()))
    return [await build_message_out(db, message, chat, user.id) for message in messages]


ExportFormat = Literal["json", "html"]


def _export_html(chat_title: str, exported_at: str, messages: list[MessageOut]) -> str:
    rows = []
    for m in messages:
        sender = html_lib.escape(m.sender_public_id or "—")
        when = html_lib.escape(m.created_at.isoformat(timespec="seconds"))
        if m.deleted_for_all:
            body = "<em>Сообщение удалено</em>"
        else:
            body = html_lib.escape(m.body or f"[{m.type.value}]").replace("\n", "<br>")
            for attachment in m.attachments:
                name = html_lib.escape(attachment.original_name or attachment.public_id)
                body += f'<br><a href="{html_lib.escape(attachment.url)}">{name}</a>'
        rows.append(
            f'<div class="msg"><span class="meta">{when} — {sender}</span>'
            f'<div class="body">{body}</div></div>'
        )

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{html_lib.escape(chat_title)} — экспорт истории</title>
<style>
  body {{ font-family: -apple-system, Arial, sans-serif; max-width: 720px; margin: 2rem auto;
          padding: 0 1rem; color: #181b1f; }}
  h1 {{ font-size: 1.25rem; }}
  .exported-at {{ color: #6d757d; font-size: 0.85rem; margin-bottom: 1.5rem; }}
  .msg {{ padding: 0.5rem 0; border-bottom: 1px solid #e5e7eb; }}
  .meta {{ font-size: 0.8rem; color: #6d757d; }}
  .body {{ margin-top: 2px; white-space: pre-wrap; }}
</style>
</head>
<body>
<h1>{html_lib.escape(chat_title)}</h1>
<div class="exported-at">Экспортировано: {html_lib.escape(exported_at)}</div>
{"".join(rows)}
</body>
</html>"""


@router.get("/{chat_public_id}/export")
async def export_chat(
    chat_public_id: str,
    format: ExportFormat = Query(default="json"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    chat, _member = await get_membership_or_404(db, chat_public_id, user)

    result = await db.execute(
        select(Message).where(Message.chat_id == chat.id).order_by(Message.id)
    )
    messages = [await build_message_out(db, message, chat, user.id) for message in result.scalars()]
    chat_title = chat.title or "Диалог"
    exported_at = datetime.now(UTC).isoformat(timespec="seconds")

    if format == "html":
        content = _export_html(chat_title, exported_at, messages)
        media_type = "text/html"
        filename = f"chat-{chat.public_id}.html"
    else:
        export = {
            "chat": {"public_id": chat.public_id, "type": chat.type.value, "title": chat_title},
            "exported_at": exported_at,
            "exported_by": user.public_id,
            "messages": [m.model_dump(mode="json") for m in messages],
        }
        content = json.dumps(export, ensure_ascii=False, indent=2)
        media_type = "application/json"
        filename = f"chat-{chat.public_id}.json"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
