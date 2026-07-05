"""Initial schema — выполняет замороженный снимок db/schema.sql целиком.

См. ADR-004 в docs/DECISIONS.md: миграция не дублирует DDL через op.create_table,
а прогоняет эталонный db/schema.sql, чтобы исключить любое расхождение между
схемой и миграцией.

asyncpg не умеет выполнять несколько SQL-команд в одном prepared statement
("cannot insert multiple commands into a prepared statement"), поэтому файл
разбивается на отдельные операторы; разбиение учитывает блоки `$$...$$`
(тело plpgsql-функций), где могут встречаться "свои" точки с запятой.

Важно (см. ADR-012): эта миграция читает не текущий db/schema.sql, а его
замороженную копию в ../snapshots/0001_schema.sql. Если читать живой файл,
любая последующая правка db/schema.sql молча меняет то, что делает уже
"выполненная" миграция 0001 — и следующая дельта-миграция (например, 0002)
падает с "column already exists", потому что 0001 успела добавить её сама.
Дельты последующих изменений схемы вносятся новыми миграциями (0002+),
а не правкой этого файла.

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

_SCHEMA_SQL_PATH = Path(__file__).resolve().parent.parent / "snapshots" / "0001_schema.sql"


def _split_sql_statements(sql: str) -> list[str]:
    """Делит SQL-скрипт на отдельные команды по ';', игнорируя ';' внутри '$$...$$'."""
    statements: list[str] = []
    buffer: list[str] = []
    in_dollar_quote = False
    i = 0
    length = len(sql)

    while i < length:
        if sql[i : i + 2] == "$$":
            in_dollar_quote = not in_dollar_quote
            buffer.append("$$")
            i += 2
            continue
        char = sql[i]
        if char == ";" and not in_dollar_quote:
            buffer.append(";")
            statement = "".join(buffer).strip()
            if statement and statement != ";":
                statements.append(statement)
            buffer = []
        else:
            buffer.append(char)
        i += 1

    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def upgrade() -> None:
    sql = _SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    bind = op.get_bind()
    for statement in _split_sql_statements(sql):
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql("DROP SCHEMA public CASCADE")
    bind.exec_driver_sql("CREATE SCHEMA public")
