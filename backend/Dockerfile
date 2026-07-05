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

# Shell form (не exec) — нужно для подстановки $PORT: Render задаёт свой PORT для
# Docker-сервисов, локально/на VPS переменная не задана и используется дефолт 8000.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
