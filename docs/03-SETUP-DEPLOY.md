# SPI Messenger — Установка, подключение БД и деплой (v1.0)

Инструкция покрывает три сценария: локальная разработка, демо-деплой (Vercel + Render + Neon Postgres) и продакшен на собственном VPS. БД везде — PostgreSQL 16, поэтому демо и прод не отличаются ничем, кроме адресов в `.env`.

---

## 1. Переменные окружения

Все секреты — только в `.env` (файл в `.gitignore`). Шаблон — `.env.example`:

```env
# --- База данных (PostgreSQL 16 везде) ---
# Демо (Neon, через Vercel Storage):
DATABASE_URL=postgresql+asyncpg://user:PASSWORD@ep-xxxx.neon.tech:5432/neondb
# Прод (контейнер на VPS):
# DATABASE_URL=postgresql+asyncpg://spi_app:PASSWORD@postgres:5432/spi_messenger

# --- Безопасность ---
JWT_SECRET=            # openssl rand -hex 32 (на Render — generateValue в render.yaml)
JWT_ACCESS_TTL_MIN=15
JWT_REFRESH_TTL_DAYS=30

# --- Файловое хранилище ---
STORAGE_BACKEND=local             # local | supabase (supabase — ещё не реализован, см. 3.4) | s3
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

## 3. Демо-деплой (Vercel + Render + Neon Postgres)

> См. `docs/DECISIONS.md`, ADR-007: по запросу заказчика БД для теста — Neon Postgres,
> подключаемый через вкладку **Storage** проекта на Vercel. API по-прежнему не может
> жить на самом Vercel (serverless-функции не держат постоянные WS-соединения, см.
> `docs/02-ARCHITECTURE.md` §1) — он разворачивается на Render, подключаясь к той же
> Neon БД. В репозитории уже есть `render.yaml` (Render Blueprint) и `frontend/vercel.json`
> (SPA-рероутинг для client-side маршрутов React Router), которые сводят ручную часть
> ниже к вводу нескольких значений в веб-интерфейсах — сами аккаунты Vercel/Render/Neon
> и клики в их дашбордах должен сделать владелец проекта.

Порядок (важно соблюдать — DATABASE_URL для Render появляется только после шага 1,
а CORS_ORIGINS/FRONTEND_URL для Render — только после шага 3):

### 3.1 Neon Postgres через Vercel (БД) — сделать первым
1. https://vercel.com → создать проект из репозитория `xghostyyy/spi`, Root Directory
   `frontend` (Vercel подхватит `frontend/vercel.json` автоматически, Framework — Vite,
   Build/Output определятся сами).
2. В том же проекте → **Storage** → **Create Database** → **Neon** (или **Postgres**,
   если маркетплейс предложит другое имя) → создать в регионе рядом с будущим Render-сервисом.
3. Скопировать pooled connection string, заменить префикс `postgresql://` на
   `postgresql+asyncpg://` — это будущий `DATABASE_URL` для Render (шаг 3.2).

### 3.2 Render (FastAPI + WebSocket) — Blueprint из render.yaml
1. https://render.com → New → **Blueprint** → подключить репозиторий `xghostyyy/spi`.
   Render найдёт `render.yaml` в корне и предложит создать сервис `spi-api`
   (Docker, `backend/Dockerfile`, `JWT_SECRET` сгенерируется автоматически).
2. Перед первым деплоем в Environment добавить вручную (помечены `sync: false` в
   `render.yaml`, Render запросит их при создании из Blueprint):
   - `DATABASE_URL` — строка из шага 3.1.
   - `CORS_ORIGINS`, `FRONTEND_URL` — временно `http://localhost:5173`, обновить после шага 3.3.
   - `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD` — можно оставить пустыми: код входа тогда
     просто печатается в лог сервиса (Render → Logs), реальные письма не отправляются.
   - `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` — можно оставить пустыми до фазы 5 (push).
   - `REDIS_URL` — оставить пустым (не обязателен при одном инстансе, см. `docs/02-ARCHITECTURE.md` §4.2).
3. После первого деплоя выполнить миграции: Render → сервис `spi-api` → Shell →
   `alembic upgrade head`.
4. Скопировать URL сервиса, например `https://spi-api.onrender.com`.

> Free-план Render засыпает после 15 минут простоя (первый запрос ~30 сек). Для показа
> клиенту — разбудить заранее или взять Starter-план. Free-план не даёт постоянный диск:
> `STORAGE_BACKEND=local` (аватары) не переживёт редеплой/рестарт — ожидаемо для тестового
> деплоя; для устойчивого хранения — Render Disk (платно) или Supabase Storage (см. 3.4).

### 3.3 Vercel — переменные фронтенда и финальный CORS
1. В проекте на Vercel (создан в шаге 3.1) → Settings → Environment Variables:
   `VITE_API_URL=https://spi-api.onrender.com`,
   `VITE_WS_URL=wss://spi-api.onrender.com/ws`, `VITE_VAPID_PUBLIC_KEY=` (пусто пока).
2. Redeploy фронта (Vercel → Deployments → Redeploy), получить итоговый домен,
   например `https://spi-messenger.vercel.app`.
3. Вернуться в Render (шаг 3.2) и обновить `CORS_ORIGINS` и `FRONTEND_URL` на этот домен.

### 3.4 Supabase (Storage) — не реализовано, только на будущее
Чтобы аватары/медиа переживали редеплой Render без платного диска, нужен внешний
storage. `STORAGE_BACKEND=supabase` в `backend/app/services/storage.py` пока —
заглушка (`NotImplementedError`); переключать `STORAGE_BACKEND` на `supabase` рано,
это отдельная задача разработки. До неё — либо мириться с потерей аватаров при
редеплое (тестовый деплой), либо подключить платный Render Disk.

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
