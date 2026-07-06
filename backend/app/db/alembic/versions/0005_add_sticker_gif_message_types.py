"""Add 'sticker' / 'gif' values to message_type (Фаза 6: стикеры и GIF).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE не может выполняться в той же транзакции, где
    # значение затем используется — но эта миграция только добавляет значения,
    # ничего ими не заполняет, так что коммит транзакции upgrade() достаточен.
    op.execute("ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'sticker'")
    op.execute("ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'gif'")


def downgrade() -> None:
    # PostgreSQL не поддерживает удаление значения enum — откат недоступен.
    raise NotImplementedError("downgrade не поддерживается: Postgres не умеет DROP VALUE у enum")
