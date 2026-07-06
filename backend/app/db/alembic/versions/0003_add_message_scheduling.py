"""Add messages.scheduled_at / scheduled_broadcast_at (Фаза 6: отложенная отправка).

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "messages", sa.Column("scheduled_broadcast_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "idx_messages_scheduled_pending",
        "messages",
        ["scheduled_at"],
        postgresql_where=sa.text("scheduled_at IS NOT NULL AND scheduled_broadcast_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_messages_scheduled_pending", table_name="messages")
    op.drop_column("messages", "scheduled_broadcast_at")
    op.drop_column("messages", "scheduled_at")
