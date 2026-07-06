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
JWT_SECRET=            # openssl rand -hex 32 (на Render — generateValue в render.yaml)
JWT_ACCESS_TTL_MIN=15
JWT_REFRESH_TTL_DAYS=30

# --- Файловое хранилище ---
STORAGE_BACKEND=local             # local | supabase (supabase — ещё не реализован, см. 3.4) | s3
SUPABASE_URL=
SUPABASE_SERVICE_KEY=             # только на сервере, никогда во фронт!
STORAGE_LOCAL_PATH=/data/uploads  # для STORAGE_BACKEND=local

# --- Почта (коды входа) — smtp.bz, домен-отправитель spi-2015.ru, см. §1.1 ---
SMTP_HOST=smtp.bz
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
MAIL_FROM=noreply@spi-2015.ru

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
```

VAPID public key фронтенд не хранит в `.env` — получает его в рантайме через
`GET /api/v1/push/vapid-public-key` (см. §3.5), чтобы значение не дублировалось
между Vercel и Render и не требовало ребилда фронта при ротации ключей.

### 1.1 SMTP (smtp.bz, домен spi-2015.ru)

Коды входа отправляются через `smtp.bz` (SMTP-релей) от имени домена `spi-2015.ru`.
Приложение не привязано к этому провайдеру — `backend/app/services/mail.py` шлёт
письма через стандартный `aiosmtplib` (`STARTTLS`) по значениям из `.env`, так что
провайдера можно сменить, просто поменяв `SMTP_*`. Если `SMTP_HOST` пуст — код входа
просто пишется в лог сервера (`[DEV] Login code for ...`), реальные письма не уходят;
это нормальный режим для локальной разработки.

Для демо/прод-деплоя:
1. Зайти в личный кабинет smtp.bz → раздел SMTP-авторизации, взять `SMTP_USER`/
   `SMTP_PASSWORD` (логин и пароль именно для SMTP, не пароль от кабинета).
   `SMTP_HOST=smtp.bz`, `SMTP_PORT=587` — значения из шаблона `.env.example` уже
   подставлены, менять не нужно, если в кабинете не указано иное.
2. Домен-отправитель `spi-2015.ru` должен быть подтверждён в кабинете smtp.bz
   (обычно — добавление SPF/DKIM TXT-записей в DNS домена), иначе письма будут
   уходить в спам или отклоняться принимающими серверами. Это разовая настройка на
   стороне DNS `spi-2015.ru`, вне репозитория.
3. `MAIL_FROM` — любой адрес на подтверждённом домене, например
   `noreply@spi-2015.ru`; должен совпадать с доменом, подтверждённым в шаге 2.
4. Проверить: `POST /api/v1/auth/request-code` с реальным e-mail — письмо должно
   дойти за несколько секунд. Если нет — проверить `SMTP_USER`/`SMTP_PASSWORD` и
   статус подтверждения домена в кабинете smtp.bz, а не код приложения (это первое,
   что стоит перепроверить при жалобах «код не пришёл» после деплоя).

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

## 3. Демо-деплой (Vercel + Render + Supabase)

### Почему не «только Vercel + Supabase»

Заказчик изначально просил ограничиться Vercel + Supabase без Neon — это сделано
(ADR-013: БД, а в перспективе и файловое хранилище, на Supabase). Но полностью убрать
Render нельзя без переписывания real-time слоя приложения:

- Бэкенд (`backend/`, FastAPI) держит **одно постоянное WebSocket-соединение на
  клиента** (`/ws`, см. `docs/02-ARCHITECTURE.md` §1 и `backend/app/ws/`) — через него
  идут новые сообщения, статусы прочтения, typing-индикатор, presence (онлайн/оффлайн),
  события чатов. Соединение живёт в памяти процесса (`ConnectionManager`), пока клиент
  не отключится.
- Vercel Serverless/Edge Functions (включая Python-рантайм) устроены иначе: функция
  поднимается на входящий запрос и завершается, отдав ответ — она физически не может
  держать сокет открытым между запросами. WebSocket на Vercel для такого бэкенда
  не работает — соединение будет обрываться сразу или почти сразу.
- Поэтому FastAPI+WS разворачивается на Render (обычный долгоживущий процесс/контейнер,
  а не serverless-функция), подключаясь к тому же Supabase Postgres, что и всё
  остальное. Vercel в этой схеме отвечает только за статику фронтенда.

Итоговое разделение ответственности: **Vercel** — только фронтенд (статика +
`frontend/vercel.json` SPA-рероутинг), **Render** — FastAPI + WebSocket API, **Supabase**
— Postgres (и в будущем Storage). Смена Render на другой хостинг с тем же свойством
«держит долгоживущий процесс» (VPS, Fly.io, Railway) возможна — это не привязка к
конкретному вендору, а требование к типу хостинга; `render.yaml` в этом случае просто
не используется, а `backend/Dockerfile` подходит для любого Docker-хостинга без правок.

> В репозитории уже есть `render.yaml` (Render Blueprint) и `frontend/vercel.json`
> (SPA-рероутинг для client-side маршрутов React Router), которые сводят ручную часть
> ниже к вводу нескольких значений в веб-интерфейсах — сами аккаунты
> Vercel/Render/Supabase и клики в их дашбордах должен сделать владелец проекта.

Порядок (важно соблюдать — DATABASE_URL для Render появляется только после шага 1,
а CORS_ORIGINS/FRONTEND_URL для Render — только после шага 3):

### 3.1 Supabase (БД) — сделать первым
1. https://supabase.com → **New project** (регион — ближе к будущему Render-сервису,
   например Frankfurt/EU). Задать и сохранить пароль БД.
2. Settings → Database → **Connection string** (URI, режим **Session**, порт 5432 —
   для приложения с длинными соединениями; для serverless-клиентов Supabase
   рекомендует pooler-порт 6543/transaction, но нашему постоянно работающему API
   на Render нужен обычный session-режим).
3. Заменить префикс `postgresql://` на `postgresql+asyncpg://` — это будущий
   `DATABASE_URL` для Render (шаг 3.2).
4. (Опционально, на будущее) Settings → API → скопировать `SUPABASE_URL` и
   `service_role key` (→ `SUPABASE_SERVICE_KEY`, только в бэкенд!) — понадобятся,
   когда будет реализован `STORAGE_BACKEND=supabase` (см. врезку в конце 3.2).

### 3.2 Render (FastAPI + WebSocket) — Blueprint из render.yaml
1. https://render.com → New → **Blueprint** → подключить репозиторий `xghostyyy/spi`.
   Render найдёт `render.yaml` в корне и предложит создать сервис `spi-api`
   (Docker, `backend/Dockerfile`, `JWT_SECRET` сгенерируется автоматически).
2. Перед первым деплоем в Environment добавить вручную (помечены `sync: false` в
   `render.yaml`, Render запросит их при создании из Blueprint):
   - `DATABASE_URL` — строка из шага 3.1.
   - `CORS_ORIGINS`, `FRONTEND_URL` — временно `http://localhost:5173`, обновить после шага 3.3.
   - `SMTP_HOST=smtp.bz`, `SMTP_USER`/`SMTP_PASSWORD` — из кабинета smtp.bz (см. §1.1);
     `MAIL_FROM=noreply@spi-2015.ru`. Можно оставить пустыми — тогда код входа просто
     печатается в лог сервиса (Render → Logs), реальные письма не отправляются
     (нормально для быстрой проверки, не годится для показа заказчику).
   - `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` — сгенерировать `npx web-push generate-vapid-keys`
     (см. §3.5); пустые значения тоже допустимы — push тогда тихо не отправляется
     (`app/services/push.py` делает ранний `return`), остальное приложение не ломается.
   - `REDIS_URL` — оставить пустым (не обязателен при одном инстансе, см. `docs/02-ARCHITECTURE.md` §4.2).
3. После первого деплоя выполнить миграции: Render → сервис `spi-api` → Shell →
   `alembic upgrade head`.
3.1. (Опционально, для показа заказчику) Наполнить демо-данными — `db/seed.sql`
   (5 вымышленных пользователей, личные и групповой чаты, опрос, закреп; см. комментарий
   в начале файла — под эти аккаунты нельзя войти по e-mail-коду, они только для вида).
   Скрипт идемпотентен (`ON CONFLICT ... DO NOTHING` везде), безопасно запускать повторно.
   Выполнить через Supabase SQL Editor (вставить содержимое файла и запустить) — Render
   Shell для этого не нужен, `psql` в контейнере может не быть.
4. Скопировать URL сервиса, например `https://spi-api.onrender.com`.

> Free-план Render засыпает после 15 минут простоя (первый запрос ~30 сек). Для показа
> клиенту — разбудить заранее или взять Starter-план. Free-план не даёт постоянный диск:
> `STORAGE_BACKEND=local` (аватары) не переживёт редеплой/рестарт — ожидаемо для тестового
> деплоя. `STORAGE_BACKEND=supabase` в `backend/app/services/storage.py` пока заглушка
> (`NotImplementedError`) — реализация Supabase Storage (buckets `avatars`/`media`,
> `SUPABASE_URL`+`SUPABASE_SERVICE_KEY` из шага 3.1.4) остаётся отдельной задачей.

### 3.3 Vercel — фронтенд и финальный CORS
1. https://vercel.com → Add New Project → репозиторий `xghostyyy/spi`, Root Directory
   `frontend` (Vercel подхватит `frontend/vercel.json` автоматически, Framework — Vite,
   Build/Output определятся сами).
2. Settings → Environment Variables: `VITE_API_URL=https://spi-api.onrender.com`,
   `VITE_WS_URL=wss://spi-api.onrender.com/ws`.
3. Deploy → получить домен, например `https://spi-messenger.vercel.app`.
4. Вернуться в Render (шаг 3.2) и обновить `CORS_ORIGINS` и `FRONTEND_URL` на этот домен.

### 3.4 Проверка на iPhone
1. Открыть URL в Safari → Поделиться → **«На экран "Домой"»**.
2. Запустить с домашнего экрана (standalone-режим).
3. В настройках приложения включить уведомления → разрешить push.
4. Отправить сообщение со второго устройства → push должен прийти при закрытом приложении.

### 3.5 Web Push (VAPID-ключи)
1. Сгенерировать пару ключей локально: `npx web-push generate-vapid-keys` (пакет
   `web-push`, ничего устанавливать в проект не нужно — `npx` скачает временно).
2. В Render (сервис `spi-api`, шаг 3.2) добавить `VAPID_PUBLIC_KEY` и
   `VAPID_PRIVATE_KEY` из вывода команды, `VAPID_SUBJECT=mailto:admin@spi-2015.ru`
   (email или URL — по спецификации VAPID; используется провайдерами push-сервисов
   для связи с владельцем в случае проблем, не показывается пользователю).
3. На Vercel ничего добавлять не нужно — фронтенд получает публичный ключ через
   `GET /api/v1/push/vapid-public-key` (см. §1), а не через свою переменную окружения.
4. Если ключи не заданы — `POST .../messages` продолжает работать как обычно, просто
   push никому не уходит (`app/services/push.py::send_push_to_user` возвращает
   раньше срока при пустом `VAPID_PRIVATE_KEY`); это безопасный дефолт для
   промежуточных проверок деплоя без push.

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
| Push не приходит вообще (не только iPhone) | `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` пусты на Render (см. §3.5) — отправка молча пропускается |
| Код входа на e-mail не приходит | Проверить `SMTP_USER`/`SMTP_PASSWORD` и статус подтверждения домена `spi-2015.ru` в кабинете smtp.bz (см. §1.1), не код приложения; если `SMTP_HOST` пуст — код печатается только в лог Render |
| WS постоянно отваливается на Render | Free-план уснул; включить keep-alive ping или платный план |
| `Access-Control-Allow-Origin` ошибки | Домен фронта не добавлен в `CORS_ORIGINS` |
| `Too many connections` Postgres | Уменьшить pool_size SQLAlchemy; на Supabase — подключаться через пулер (порт 6543, режим transaction) |
| iOS: контент под чёлкой | Проверить `viewport-fit=cover` и `env(safe-area-inset-*)` |
