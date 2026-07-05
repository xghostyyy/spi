"""Чёрный список пользователей."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models import BlockedUser, File, User
from app.db.session import get_db

router = APIRouter(prefix="/blocks", tags=["blocks"])


class BlockBody(BaseModel):
    username: str


class BlockedUserOut(BaseModel):
    public_id: str
    username: str | None
    display_name: str
    avatar_url: str | None


@router.get("", response_model=list[BlockedUserOut])
async def list_blocked(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[BlockedUserOut]:
    result = await db.execute(
        select(User, File)
        .join(BlockedUser, BlockedUser.blocked_id == User.id)
        .outerjoin(File, File.id == User.avatar_file_id)
        .where(BlockedUser.owner_id == user.id)
        .order_by(User.display_name)
    )
    return [
        BlockedUserOut(
            public_id=blocked_user.public_id,
            username=blocked_user.username,
            display_name=blocked_user.display_name,
            avatar_url=f"/media/{avatar.storage_key}" if avatar else None,
        )
        for blocked_user, avatar in result.all()
    ]


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def block_user(
    body: BlockBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    username = body.username.strip().lstrip("@")
    result = await db.execute(select(User.id).where(User.username == username))
    target_id = result.scalar_one_or_none()
    if target_id is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "Пользователь не найден"},
        )
    if target_id == user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "self_block", "message": "Нельзя заблокировать себя"},
        )
    stmt = (
        pg_insert(BlockedUser)
        .values(owner_id=user.id, blocked_id=target_id, created_at=datetime.now(UTC))
        .on_conflict_do_nothing(index_elements=["owner_id", "blocked_id"])
    )
    await db.execute(stmt)
    await db.commit()


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_user(
    public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(User.id).where(User.public_id == public_id))
    target_id = result.scalar_one_or_none()
    if target_id is None:
        return
    await db.execute(
        delete(BlockedUser).where(
            BlockedUser.owner_id == user.id, BlockedUser.blocked_id == target_id
        )
    )
    await db.commit()
