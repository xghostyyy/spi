"""Initial schema — выполняет db/schema.sql целиком.

См. ADR-004 в docs/DECISIONS.md: миграция не дублирует DDL через op.create_table,
а прогоняет эталонный db/schema.sql, чтобы исключить любое расхождение между
схемой и миграцией.

Revision ID: 0001
Revises:
Create Date: 2026-07-05
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# backend/app/db/alembic/versions/0001_initial_schema.py -> repo root -> db/schema.sql
_SCHEMA_SQL_PATH = Path(__file__).resolve().parents[5] / "db" / "schema.sql"


def upgrade() -> None:
    sql = _SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    op.get_bind().exec_driver_sql(sql)


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
