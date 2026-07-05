"""Add files.original_name (Фаза 3: имя файла-документа у отправителя).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("files", sa.Column("original_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("files", "original_name")
