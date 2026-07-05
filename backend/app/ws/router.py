"""WebSocket-эндпоинт /ws: единый канал real-time событий (см. docs/API.md)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.security import decode_ws_ticket
from app.db.models import Chat, ChatMember, Message, User
from app.db.session import SessionLocal
from app.services.chat import get_direct_peer_user_ids
from app.ws.manager import manager

router = APIRouter()
logger = logging.getLogger("spi.ws")


async def _resolve_user(user_public_id: str) -> User | None:
    async with SessionLocal() as db:
        result = await db.execute(
            select(User).where(User.public_id == user_public_id, User.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()


async def _broadcast_presence(
    user_id: int, user_public_id: str, online: bool, last_seen_at: datetime | None
) -> None:
    async with SessionLocal() as db:
        peer_ids = await get_direct_peer_user_ids(db, user_id)
    payload = {
        "user_public_id": user_public_id,
        "online": online,
        "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
    }
    await manager.send_to_users(peer_ids, "presence", payload)


async def _handle_typing(user_id: int, user_public_id: str, payload: dict[str, object]) -> None:
    chat_public_id = payload.get("chat_id")
    if not isinstance(chat_public_id, str):
        return
    async with SessionLocal() as db:
        chat_result = await db.execute(select(Chat.id).where(Chat.public_id == chat_public_id))
        chat_id = chat_result.scalar_one_or_none()
        if chat_id is None:
            return
        member_result = await db.execute(
            select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
        )
        member_ids = list(member_result.scalars().all())
        if user_id not in member_ids:
            return
        peer_ids = [uid for uid in member_ids if uid != user_id]

    await manager.send_to_users(
        peer_ids,
        "typing",
        {
            "chat_id": chat_public_id,
            "user_public_id": user_public_id,
            "kind": payload.get("kind", "text"),
            "active": bool(payload.get("active", False)),
        },
    )


async def _handle_read(user_id: int, user_public_id: str, payload: dict[str, object]) -> None:
    chat_public_id = payload.get("chat_id")
    message_public_id = payload.get("message_id")
    if not isinstance(chat_public_id, str) or not isinstance(message_public_id, str):
        return

    async with SessionLocal() as db:
        chat_result = await db.execute(select(Chat).where(Chat.public_id == chat_public_id))
        chat = chat_result.scalar_one_or_none()
        if chat is None:
            return
        member_result = await db.execute(
            select(ChatMember).where(ChatMember.chat_id == chat.id, ChatMember.user_id == user_id)
        )
        member = member_result.scalar_one_or_none()
        if member is None:
            return
        message_result = await db.execute(
            select(Message.id).where(
                Message.public_id == message_public_id, Message.chat_id == chat.id
            )
        )
        message_id = message_result.scalar_one_or_none()
        if message_id is None:
            return
        if member.last_read_message_id is None or message_id > member.last_read_message_id:
            member.last_read_message_id = message_id
            await db.commit()
        peers_result = await db.execute(
            select(ChatMember.user_id).where(
                ChatMember.chat_id == chat.id, ChatMember.user_id != user_id
            )
        )
        peer_ids = list(peers_result.scalars().all())

    await manager.send_to_users(
        peer_ids,
        "read.updated",
        {
            "chat_id": chat_public_id,
            "user_public_id": user_public_id,
            "last_read_message_id": message_id,
        },
    )


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, ticket: str = Query(...)) -> None:
    try:
        user_public_id = decode_ws_ticket(ticket)
    except jwt.InvalidTokenError:
        await websocket.close(code=4401)
        return

    user = await _resolve_user(user_public_id)
    if user is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    manager.connect(user.id, websocket)
    await _broadcast_presence(user.id, user.public_id, online=True, last_seen_at=None)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue

            event_type = event.get("type")
            payload = event.get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}

            if event_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "payload": {}, "seq": 0}))
            elif event_type == "typing":
                await _handle_typing(user.id, user.public_id, payload)
            elif event_type == "read":
                await _handle_read(user.id, user.public_id, payload)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user.id, websocket)
        if not manager.is_online(user.id):
            now = datetime.now(UTC)
            async with SessionLocal() as db:
                user_result = await db.execute(select(User).where(User.id == user.id))
                fresh_user = user_result.scalar_one_or_none()
                if fresh_user is not None:
                    fresh_user.last_seen_at = now
                    await db.commit()
            await _broadcast_presence(user.id, user.public_id, online=False, last_seen_at=now)
