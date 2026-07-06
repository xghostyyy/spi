"""Подписки на Web Push (VAPID)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.db.models import PushSubscription, User
from app.db.session import get_db

router = APIRouter(prefix="/push", tags=["push"])


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeBody(BaseModel):
    endpoint: str
    keys: SubscriptionKeys


class UnsubscribeBody(BaseModel):
    endpoint: str


@router.get("/vapid-public-key")
async def get_vapid_public_key() -> dict[str, str]:
    return {"public_key": get_settings().vapid_public_key}


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(
    body: SubscribeBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = (
        pg_insert(PushSubscription)
        .values(
            user_id=user.id,
            endpoint=body.endpoint,
            p256dh=body.keys.p256dh,
            auth=body.keys.auth,
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_update(
            index_elements=["endpoint", "user_id"],
            set_={"p256dh": body.keys.p256dh, "auth": body.keys.auth},
        )
    )
    await db.execute(stmt)
    await db.commit()


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    body: UnsubscribeBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == user.id, PushSubscription.endpoint == body.endpoint
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is not None:
        await db.delete(subscription)
        await db.commit()
