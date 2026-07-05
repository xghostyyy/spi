# SPI Messenger — Установка, подключение БД и деплой (v1.0)

Инструкция покрывает три сценария: локальная разработка, демо-деплой (Vercel + Render + Supabase) и продакшен на собственном VPS. БД везде — PostgreSQL 16, поэтому демо и прод не отличаются ничем, кроме адресов в `.env`.

---

## 1. Переменные окружения

Все секреты — только в `.env` (файл в `.gitignore`). Шаблон — `.env.example`:

```env
# --- База данных (PostgreSQL 16 везде) ---
# Демо (Supabase):
DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@db.xxxx.supabase.co:5432/postgres
# Прод (контейнер на VPS):
# DATABASE_URL=postgresql+asyncpg://spi_app:PASSWORD@postgres:5432/spi_messenger

# --- Безопасность ---
JWT_SECRET=            # openssl rand -hex 32
JWT_ACCESS_TTL_MIN=15
JWT_REFRESH_TTL_DAYS=30

# --- Файловое хранилище ---
STORAGE_BACKEND=supabase          # supabase | local | s3
SUPABASE_URL=
SUPABASE_SERVICE_KEY=             # только на сервере, никогда во фронт!
STORAGE_LOCAL_PATH=/data/uploads  # для STORAGE_BACKEND=local

# --- Почта (коды входа) ---
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
MAIL_FROM=noreply@spi-messenger.ru

# --- Web Push ---
VAPID_PUBLIC_KEY=                 # npx web-push generate-vapid-keys
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:admin@spi-messenger.ru

# --- Прочее ---
CORS_ORIGINS=https://spi-messenger.vercel.app,http://localhost:5173
REDIS_URL=                        # пусто = in-process events (1 инстанс)
FRONTEND_URL=https://spi-messenger.vercel.app
```

Фронтенд (`frontend/.env`):

```env
VITE_API_URL=https://spi-api.onrender.com
VITE_WS_URL=wss://spi-api.onrender.com/ws
VITE_VAPID_PUBLIC_KEY=            # публичный ключ можно светить
```

---

## 2. Локальная разработка

Требования: Node 20+, Python 3.12+, Docker (для БД).

```bash
git clone <REPO_URL> && cd spi-messenger

# БД + Redis + MinIO одним махом
docker compose -f docker-compose.dev.yml up -d   # postgres:16, redis, minio

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env                          # заполнить значения
alembic upgrade head                                # создать таблицы
uvicorn app.main:app --reload --port 8000

# Frontend (второй терминал)
cd frontend
npm install
npm run dev                                         # http://localhost:5173
```

Проверка с телефона в локальной сети: `npm run dev -- --host`, открыть `http://<IP-компьютера>:5173` (push и PWA-установка потребуют HTTPS — использовать `npm run dev:https` с mkcert-сертификатом или демо-деплой).

---

## 3. Демо-деплой (Vercel + Render + Postgres)

> См. `docs/DECISIONS.md`, ADR-007: по уточнению заказчика БД для теста поднимается через
> Vercel Marketplace (Neon Postgres) во вкладке **Storage** проекта на Vercel — это и
> заменяет отдельный аккаунт Supabase для БД (Storage-файлы пока остаются на
> `STORAGE_BACKEND=local` на стороне API, либо тоже через Supabase — см. 3.1).

### 3.0 Neon Postgres через Vercel (БД)
1. В проекте на https://vercel.com → **Storage** → **Create Database** → **Neon** (или
   **Postgres**, если предложен другой провайдер маркетплейса) → создать в регионе рядом с
   Render/Railway.
2. Vercel сгенерирует `DATABASE_URL`/`POSTGRES_URL` — скопировать pooled-подключение,
   заменить префикс на `postgresql+asyncpg://` для бэкенда.
3. Эту же строку указать в Environment Variables сервиса на Render/Railway (шаг 3.2) —
   Vercel-проект фронта эту переменную не использует напрямую (БД нужна только API).
4. Выполнить миграции: `alembic upgrade head` (Shell на Render или локально с этим `DATABASE_URL`).

### 3.1 Supabase (Storage, опционально)
1. https://supabase.com → New project (регион EU). Сохранить пароль БД.
2. Settings → Database → Connection string (URI, режим Session) → это `DATABASE_URL` (заменить префикс на `postgresql+asyncpg://`).
3. Storage → создать buckets: `avatars` (public), `media` (private).
4. Settings → API → скопировать `SUPABASE_URL` и `service_role key` (→ `SUPABASE_SERVICE_KEY`, только в бэкенд!).

### 3.2 Render (FastAPI + WebSocket)
1. https://render.com → New → Web Service → подключить GitHub-репозиторий.
2. Root Directory: `backend`, Runtime: Docker (в репо есть `backend/Dockerfile`).
3. Environment → добавить все переменные из раздела 1 (руками, не файлом).
4. После первого деплоя выполнить миграции: Shell → `alembic upgrade head`.
5. Скопировать URL сервиса → `https://spi-api.onrender.com`.

> Free-план Render засыпает после 15 минут простоя (первый запрос ~30 сек). Для показа клиенту — разбудить заранее или взять Starter-план. Альтернатива — Railway.

### 3.3 Vercel (фронтенд)
1. https://vercel.com → Add New Project → тот же репозиторий.
2. Root Directory: `frontend`, Framework: Vite. Build: `npm run build`, Output: `dist`.
3. Environment Variables: `VITE_API_URL`, `VITE_WS_URL`, `VITE_VAPID_PUBLIC_KEY`.
4. Deploy → получаем `https://spi-messenger.vercel.app`.
5. В Render обновить `CORS_ORIGINS` и `FRONTEND_URL` на этот домен.

### 3.4 Проверка на iPhone
1. Открыть URL в Safari → Поделиться → **«На экран "Домой"»**.
2. Запустить с домашнего экрана (standalone-режим).
3. В настройках приложения включить уведомления → разрешить push.
4. Отправить сообщение со второго устройства → push должен прийти при закрытом приложении.

---

## 4. Продакшен на VPS (PostgreSQL)

Требования: Ubuntu 22.04+, Docker + Docker Compose, домен, указывающий на VPS.

### 4.1 Подключение БД
```bash
# На VPS
git clone <REPO_URL> /opt/spi-messenger && cd /opt/spi-messenger
cp .env.example .env && nano .env
#   DATABASE_URL=postgresql+asyncpg://spi_app:<пароль>@postgres:5432/spi_messenger
#   STORAGE_BACKEND=local (или s3/minio)

docker compose up -d postgres
# Создание БД, пользователя и таблиц:
docker compose exec -T postgres psql -U postgres -f - < db/schema.sql
# (или через миграции: docker compose run --rm api alembic upgrade head)

# Демо-данные (опционально):
docker compose exec -T postgres psql -U postgres -d spi_messenger -f - < db/seed.sql
```

### 4.2 Запуск всего стека
```bash
docker compose up -d        # nginx + api + postgres + redis (+ minio)
```

`docker-compose.yml` включает: `nginx` (статика фронта + reverse proxy + WSS), `api` (FastAPI, 2 воркера), `postgres:16` (том `pg_data`), `redis`, `certbot` (авто-HTTPS). Фронт собирается в билд-стадии и кладётся в том nginx.

### 4.3 Перенос данных с демо на VPS
Диалект одинаковый, поэтому перенос тривиален:
1. `pg_dump "postgresql://postgres:PASSWORD@db.xxxx.supabase.co:5432/postgres" -Fc -f demo.dump`
2. `pg_restore -U postgres -d spi_messenger demo.dump`
3. Файлы Storage → скачать через `scripts/migrate_storage.py` в локальный том/MinIO.

### 4.4 Обслуживание
- Бэкапы: cron `pg_dump -Fc` ежедневно + копия тома uploads (пример в `scripts/backup.sh`).
- Обновление: `git pull && docker compose build && docker compose up -d && docker compose run --rm api alembic upgrade head`.
- Логи: `docker compose logs -f api`.

---

## 5. Частые проблемы

| Симптом | Причина / решение |
|---|---|
| Push не приходит на iPhone | PWA не установлена на домашний экран, iOS < 16.4, или подписка запрошена не по жесту пользователя |
| WS постоянно отваливается на Render | Free-план уснул; включить keep-alive ping или платный план |
| `Access-Control-Allow-Origin` ошибки | Домен фронта не добавлен в `CORS_ORIGINS` |
| `Too many connections` Postgres | Уменьшить pool_size SQLAlchemy; на Supabase — подключаться через пулер (порт 6543, режим transaction) |
| iOS: контент под чёлкой | Проверить `viewport-fit=cover` и `env(safe-area-inset-*)` |
