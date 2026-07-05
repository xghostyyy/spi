"""Контакты по @username. Добавление идемпотентно (INSERT ... ON CONFLICT)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models import BlockedUser, Contact, File, User
from app.db.session import get_db

router = APIRouter(prefix="/contacts", tags=["contacts"])


class AddContactBody(BaseModel):
    username: str


class ContactOut(BaseModel):
    contact_public_id: str
    username: str | None
    display_name: str
    avatar_url: str | None
    alias: str | None


def _contact_out(contact: Contact, contact_user: User, avatar_file: File | None) -> ContactOut:
    return ContactOut(
        contact_public_id=contact_user.public_id,
        username=contact_user.username,
        display_name=contact_user.display_name,
        avatar_url=f"/media/{avatar_file.storage_key}" if avatar_file else None,
        alias=contact.alias,
    )


async def _blocked_between(db: AsyncSession, user_a_id: int, user_b_id: int) -> bool:
    result = await db.execute(
        select(BlockedUser).where(
            or_(
                and_(BlockedUser.owner_id == user_a_id, BlockedUser.blocked_id == user_b_id),
                and_(BlockedUser.owner_id == user_b_id, BlockedUser.blocked_id == user_a_id),
            )
        )
    )
    return result.first() is not None


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ContactOut]:
    result = await db.execute(
        select(Contact, User, File)
        .join(User, User.id == Contact.contact_id)
        .outerjoin(File, File.id == User.avatar_file_id)
        .where(Contact.owner_id == user.id)
        .order_by(User.display_name)
    )
    return [
        _contact_out(contact, contact_user, avatar)
        for contact, contact_user, avatar in result.all()
    ]


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def add_contact(
    body: AddContactBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    username = body.username.strip().lstrip("@")
    user_result = await db.execute(select(User).where(User.username == username))
    target = user_result.scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "Пользователь не найден"},
        )
    if target.id == user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "self_contact", "message": "Нельзя добавить себя в контакты"},
        )
    if await _blocked_between(db, user.id, target.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "blocked", "message": "Недоступно из-за блокировки"},
        )

    stmt = (
        pg_insert(Contact)
        .values(owner_id=user.id, contact_id=target.id, created_at=datetime.now(UTC))
        .on_conflict_do_nothing(index_elements=["owner_id", "contact_id"])
    )
    await db.execute(stmt)
    await db.commit()

    contact_result = await db.execute(
        select(Contact).where(Contact.owner_id == user.id, Contact.contact_id == target.id)
    )
    contact = contact_result.scalar_one()
    avatar_file = None
    if target.avatar_file_id:
        avatar_result = await db.execute(select(File).where(File.id == target.avatar_file_id))
        avatar_file = avatar_result.scalar_one_or_none()
    return _contact_out(contact, target, avatar_file)


@router.delete("/{contact_public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_contact(
    contact_public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(User.id).where(User.public_id == contact_public_id))
    target_id = result.scalar_one_or_none()
    if target_id is None:
        return
    await db.execute(
        delete(Contact).where(Contact.owner_id == user.id, Contact.contact_id == target_id)
    )
    await db.commit()
