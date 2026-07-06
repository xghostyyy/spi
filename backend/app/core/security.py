"""Хэширование секретов (пароли, коды входа, refresh-токены) и работа с JWT."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()


def hash_secret(value: str) -> str:
    return _hasher.hash(value)


def verify_secret(value: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, value)
    except VerifyMismatchError:
        return False


def generate_login_code() -> str:
    """6-значный числовой код (может начинаться с нуля)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def create_access_token(user_public_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_public_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_ttl_min),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str:
    """Возвращает public_id пользователя. Бросает jwt.InvalidTokenError при проблеме."""
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    sub = payload["sub"]
    if not isinstance(sub, str):
        raise jwt.InvalidTokenError("malformed subject")
    return sub


def generate_refresh_secret() -> str:
    return secrets.token_urlsafe(48)


def generate_invite_token() -> str:
    """22 URL-safe символа (base64 без паддинга от 16 байт) — под CHAR(22) в chat_invites."""
    return secrets.token_urlsafe(16)


_WS_TICKET_TTL_SECONDS = 60


def create_ws_ticket(user_public_id: str) -> str:
    """Короткоживущий тикет для подключения к /ws (не светится в логах дольше секунд TTL)."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_public_id,
        "iat": now,
        "exp": now + timedelta(seconds=_WS_TICKET_TTL_SECONDS),
        "type": "ws",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_ws_ticket(token: str) -> str:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if payload.get("type") != "ws":
        raise jwt.InvalidTokenError("wrong token type")
    sub = payload["sub"]
    if not isinstance(sub, str):
        raise jwt.InvalidTokenError("malformed subject")
    return sub
