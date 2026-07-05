"""Общие fixtures: транзакционная БД (rollback после каждого теста) + HTTP-клиент.

Требует реальный PostgreSQL 16 по DATABASE_URL со схемой db/schema.sql
(накатывается через `alembic upgrade head`). Локально без Postgres эти тесты
не запускаются — проверяются в CI (см. docs/DECISIONS.md, ADR-002).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.main import app
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """В тестах все запросы идут с одного IP — без сброса лимитер слишком быстро
    накапливает "нарушения" между независимыми тестами (в проде разные IP)."""
    limiter.reset()


# NullPool: каждый тест pytest-asyncio может выполняться в своём event loop,
# а пул соединений SQLAlchemy по умолчанию переиспользует asyncpg-соединения
# между тестами и не привязан к loop'у, вызывавшему их создание — из-за этого
# падает "Event loop is closed". NullPool открывает новое соединение на каждый
# connect() и не хранит его между тестами, поэтому соединение всегда создаётся
# и закрывается в рамках одного и того же event loop.
_test_engine = create_async_engine(get_settings().database_url, poolclass=NullPool)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    connection = await _test_engine.connect()
    trans = await connection.begin()
    session_factory = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    session = session_factory()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        await session.close()
        await trans.rollback()
        await connection.close()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
