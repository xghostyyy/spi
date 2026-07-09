"""Add 'video_note' value to message_type (видеокружки, ADR-026).

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'video_note'")


def downgrade() -> None:
    # PostgreSQL не поддерживает удаление значения enum — откат недоступен.
    raise NotImplementedError("downgrade не поддерживается: Postgres не умеет DROP VALUE у enum")
