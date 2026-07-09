"""Add users.e2ee_public_key and chats.is_secret (Фаза 6: секретные чаты).

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("e2ee_public_key", sa.Text(), nullable=True))
    op.add_column(
        "chats",
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("chats", "is_secret")
    op.drop_column("users", "e2ee_public_key")
