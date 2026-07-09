"""Аутентификация: вход по e-mail-коду, JWT access + httpOnly refresh-cookie с ротацией."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.api.schemas import SessionOut, UserOut
from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    create_ws_ticket,
    generate_login_code,
    generate_refresh_secret,
    hash_secret,
    verify_secret,
)
from app.db.models import EmailLoginCode, File, Session, User
from app.db.session import get_db
from app.services.mail import send_login_code

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_SANITIZE_RE = re.compile(r"[^a-z0-9]+")
_CODE_TTL_MIN = 10


async def _generate_unique_username(db: AsyncSession, email: str) -> str:
    """Первичный @username из локальной части e-mail (см. правила в users.py:
    латиница/цифры/_, начинается с буквы, 3-32 символа). При коллизии — суффикс."""
    local = email.split("@", 1)[0].lower()
    base = _USERNAME_SANITIZE_RE.sub("_", local).strip("_")
    if not base or not base[0].isalpha():
        base = f"user{base}"
    base = base[:24]
    if len(base) < 3:
        base = f"{base}user"[:24]

    candidate = base
    suffix = 0
    while True:
        exists = await db.execute(select(User.id).where(User.username == candidate))
        if exists.scalar_one_or_none() is None:
            return candidate
        suffix += 1
        candidate = f"{base}{suffix}"[:32]


_MAX_CODE_ATTEMPTS = 5
_REFRESH_COOKIE = "spi_refresh"
_REFRESH_COOKIE_PATH = "/api/v1/auth"

_INVALID_CODE = HTTPException(
    status.HTTP_400_BAD_REQUEST,
    detail={"code": "invalid_code", "message": "Неверный или истёкший код"},
)
_INVALID_REFRESH = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail={"code": "invalid_refresh", "message": "Сессия недействительна"},
)


class RequestCodeBody(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email")
        return v


class VerifyCodeBody(BaseModel):
    email: str
    code: str


class AuthResponse(BaseModel):
    access_token: str
    user: UserOut


class WsTicketResponse(BaseModel):
    ticket: str


def _set_refresh_cookie(response: Response, value: str) -> None:
    if get_settings().app_env == "prod":
        response.set_cookie(
            _REFRESH_COOKIE,
            value,
            httponly=True,
            secure=True,
            samesite="none",
            path=_REFRESH_COOKIE_PATH,
        )
    else:
        response.set_cookie(
            _REFRESH_COOKIE,
            value,
            httponly=True,
            secure=False,
            samesite="lax",
            path=_REFRESH_COOKIE_PATH,
        )


async def _load_avatar(db: AsyncSession, user: User) -> File | None:
    if not user.avatar_file_id:
        return None
    result = await db.execute(select(File).where(File.id == user.avatar_file_id))
    return result.scalar_one_or_none()


@router.post("/request-code", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def request_code(
    request: Request, body: RequestCodeBody, db: AsyncSession = Depends(get_db)
) -> None:
    code = generate_login_code()
    now = datetime.now(UTC)
    db.add(
        EmailLoginCode(
            email=body.email,
            code_hash=hash_secret(code),
            expires_at=now + timedelta(minutes=_CODE_TTL_MIN),
            created_at=now,
        )
    )
    await db.commit()
    try:
        await send_login_code(body.email, code)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "mail_send_failed",
                "message": "Не удалось отправить письмо с кодом. Попробуйте ещё раз позже.",
            },
        ) from exc


@router.post("/verify-code", response_model=AuthResponse)
@limiter.limit("10/minute")
async def verify_code(
    request: Request, response: Response, body: VerifyCodeBody, db: AsyncSession = Depends(get_db)
) -> AuthResponse:
    email = body.email.strip().lower()
    code_result = await db.execute(
        select(EmailLoginCode)
        .where(EmailLoginCode.email == email, EmailLoginCode.used_at.is_(None))
        .order_by(EmailLoginCode.id.desc())
        .limit(1)
    )
    login_code = code_result.scalar_one_or_none()

    now = datetime.now(UTC)
    code_invalid = (
        login_code is None
        or login_code.expires_at < now
        or login_code.attempts >= _MAX_CODE_ATTEMPTS
    )
    if code_invalid:
        raise _INVALID_CODE
    assert login_code is not None  # сужение типа для mypy после проверки выше
    if not verify_secret(body.code.strip(), login_code.code_hash):
        login_code.attempts += 1
        await db.commit()
        raise _INVALID_CODE

    login_code.used_at = now
    await db.commit()

    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if user is None:
        user = User(
            public_id=str(ULID()),
            email=email,
            email_verified=True,
            display_name=email.split("@", 1)[0],
            username=await _generate_unique_username(db, email),
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        await db.flush()
    elif not user.email_verified:
        user.email_verified = True

    session = Session(
        user_id=user.id,
        refresh_hash="",
        device_label=(request.headers.get("user-agent") or "")[:128] or None,
        ip=request.client.host if request.client else None,
        expires_at=now + timedelta(days=get_settings().jwt_refresh_ttl_days),
        created_at=now,
        last_used_at=now,
    )
    db.add(session)
    await db.flush()

    refresh_secret = generate_refresh_secret()
    session.refresh_hash = hash_secret(refresh_secret)
    await db.commit()

    _set_refresh_cookie(response, f"{session.id}.{refresh_secret}")

    avatar_file = await _load_avatar(db, user)
    return AuthResponse(
        access_token=create_access_token(user.public_id), user=UserOut.from_model(user, avatar_file)
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> AuthResponse:
    raw = request.cookies.get(_REFRESH_COOKIE)
    if not raw or "." not in raw:
        raise _INVALID_REFRESH
    session_id_raw, secret = raw.split(".", 1)
    if not session_id_raw.isdigit():
        raise _INVALID_REFRESH

    session_result = await db.execute(select(Session).where(Session.id == int(session_id_raw)))
    session = session_result.scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at < now
        or not verify_secret(secret, session.refresh_hash)
    ):
        raise _INVALID_REFRESH

    user_result = await db.execute(
        select(User).where(User.id == session.user_id, User.is_deleted.is_(False))
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise _INVALID_REFRESH

    new_secret = generate_refresh_secret()
    session.refresh_hash = hash_secret(new_secret)
    session.last_used_at = now
    await db.commit()

    _set_refresh_cookie(response, f"{session.id}.{new_secret}")

    avatar_file = await _load_avatar(db, user)
    return AuthResponse(
        access_token=create_access_token(user.public_id), user=UserOut.from_model(user, avatar_file)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    raw = request.cookies.get(_REFRESH_COOKIE)
    if raw and "." in raw:
        session_id_raw, _secret = raw.split(".", 1)
        if session_id_raw.isdigit():
            result = await db.execute(select(Session).where(Session.id == int(session_id_raw)))
            session = result.scalar_one_or_none()
            if session is not None and session.revoked_at is None:
                session.revoked_at = datetime.now(UTC)
                await db.commit()
    response.delete_cookie(_REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)


def _current_session_id(request: Request) -> int | None:
    raw = request.cookies.get(_REFRESH_COOKIE)
    if not raw or "." not in raw:
        return None
    session_id_raw, _secret = raw.split(".", 1)
    return int(session_id_raw) if session_id_raw.isdigit() else None


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SessionOut]:
    current_id = _current_session_id(request)
    now = datetime.now(UTC)
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None), Session.expires_at > now)
        .order_by(Session.last_used_at.desc())
    )
    return [
        SessionOut(
            id=session.id,
            device_label=session.device_label,
            ip=session.ip,
            created_at=session.created_at,
            last_used_at=session.last_used_at,
            is_current=session.id == current_id,
        )
        for session in result.scalars().all()
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: int,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "session_not_found", "message": "Сессия не найдена"},
        )
    if session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        await db.commit()

    if session_id == _current_session_id(request):
        response.delete_cookie(_REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)


@router.post("/ws-ticket", response_model=WsTicketResponse)
async def issue_ws_ticket(user: User = Depends(get_current_user)) -> WsTicketResponse:
    return WsTicketResponse(ticket=create_ws_ticket(user.public_id))
