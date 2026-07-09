FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY alembic.ini* ./

EXPOSE 8000

# ВАЖНО: строго --workers 1. Приложение держит WebSocket ConnectionManager и
# фоновый планировщик отложенных сообщений В ПАМЯТИ ПРОЦЕССА (см. ADR-018, ADR-023).
# При >1 воркере real-time не пересекается между воркерами, а отложенные сообщения
# доставляются дважды. Горизонтальное масштабирование потребует Redis Pub/Sub —
# пока не требуется (один инстанс).
#
# Shell form (не exec) — для подстановки ${PORT:-8000}; на VPS PORT не задан → 8000.
# alembic upgrade head на старте: миграции накатываются при каждом деплое.
CMD sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
