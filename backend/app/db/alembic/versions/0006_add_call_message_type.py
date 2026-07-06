"""Add 'call' value to message_type (Фаза 6: звонки WebRTC).

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'call'")


def downgrade() -> None:
    # PostgreSQL не поддерживает удаление значения enum — откат недоступен.
    raise NotImplementedError("downgrade не поддерживается: Postgres не умеет DROP VALUE у enum")
