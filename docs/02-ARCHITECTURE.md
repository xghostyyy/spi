# SPI Messenger — Архитектура (v1.0)

## 1. Стек

| Слой | Технология | Обоснование |
|---|---|---|
| Frontend | **React 18 + Vite + TypeScript** | Быстрая сборка, экосистема, PWA-плагин |
| Стили | CSS-переменные (дизайн-токены) + CSS Modules | Точное соответствие макетам, две темы без перегенерации |
| Состояние | Zustand + TanStack Query | Простое глобальное состояние + кэш серверных данных |
| Real-time | WebSocket (native) + переподключение | Единый канал событий |
| Backend | **Python 3.12 + FastAPI** | Async, WebSocket из коробки, OpenAPI автоматически |
| ORM | **SQLAlchemy 2 (async) + Alembic** | Миграции, типобезопасность |
| БД | **PostgreSQL 16 везде** (контейнер в том же compose; managed — опционально) | Один диалект демо=прод, русский полнотекстовый поиск, JSONB; переезд = `pg_dump`/`pg_restore` |
| Файлы | Локальный диск (постоянный том `uploads`) / MinIO / S3 | Абстракция StorageService |
| Push | Web Push (pywebpush, VAPID) | Работает на iOS PWA 16.4+ |
| Почта | SMTP (aiosmtplib) / Resend API | Коды входа |
| Кэш/PubSub | Redis (опционально в MVP; обязателен при >1 инстанса API) | Fan-out WS-событий |
| Деплой демо и prod | **Один VPS: Docker Compose (Caddy + api + postgres)** | Единый стек, `docker compose up -d`, авто-HTTPS (ADR-023) |

> **Почему всё на одном сервере (ADR-023):** приложению нужен long-lived процесс —
> постоянный WebSocket и фоновый планировщик живут в памяти процесса. Один VPS + Caddy
> (авто-HTTPS, единый origin) закрывает это без serverless-ограничений и без CORS;
> тот же стек — и для демо, и для прода. Подробности деплоя — `docs/03-SETUP-DEPLOY.md`.

## 2. Схема системы

```
   iPhone PWA ────┐        ┌──────────── один VPS (Docker Compose) ────────────┐
   Android PWA ───┼──────► │  Caddy :443 — авто-HTTPS, единый origin            │
   Desktop Web ───┘  https │    /              → статика фронта (React SPA/PWA) │
                       wss  │    /api /ws /media → api:8000                      │
                           │  FastAPI (REST + WebSocket + планировщик, 1 воркер) │
                           │      ├─ Postgres 16 (том pg_data)                   │
                           │      └─ файлы: том uploads (диск) / MinIO / S3      │
                           └────────────────────────────────────────────────────┘
                        + SMTP (коды входа) + Web Push (VAPID)
   Redis (pubsub) — не нужен при одном инстансе; добавляется при масштабировании.
```

## 3. Структура репозитория (monorepo)

```
spi-messenger/
├── frontend/                 # React + Vite + TS
│   ├── src/
│   │   ├── app/              # роутер, провайдеры, темы
│   │   ├── shared/           # ui-kit (Button, Avatar, Input...), дизайн-токены, api-клиент, ws-клиент
│   │   ├── entities/         # user, chat, message (модели + сторы)
│   │   ├── features/         # auth, send-message, reactions, search, settings...
│   │   ├── pages/            # ChatListPage, ChatPage, SettingsPage, AuthPage
│   │   └── pwa/              # service worker, push-подписка, manifest
│   └── public/               # иконки, splash, apple-touch-icon
├── backend/                  # FastAPI
│   ├── app/
│   │   ├── api/              # роутеры: auth, users, contacts, chats, messages, files, search, push
│   │   ├── core/             # config (pydantic-settings), security (JWT), deps
│   │   ├── db/               # модели SQLAlchemy, session, alembic/
│   │   ├── services/         # auth, chat, message, storage, mail, push, presence
│   │   ├── ws/               # менеджер соединений, протокол событий, redis pubsub
│   │   └── main.py
│   └── tests/
├── db/
│   ├── schema.sql            # PostgreSQL 16 — готовый скрипт создания БД
│   └── seed.sql              # демо-данные
├── docs/                     # ТЗ, архитектура, инструкции, API
├── docker-compose.yml        # prod-профиль VPS
├── docker-compose.dev.yml    # локальная разработка
└── .env.example              # все переменные, без значений
```

## 4. Ключевые решения

### 4.1 База данных: PostgreSQL 16 везде
- Один диалект в демо (Supabase) и проде (контейнер на VPS): нулевая разница окружений, переезд — `pg_dump | pg_restore`.
- ID — `BIGINT IDENTITY` (+ публичные `public_id CHAR(26)` ULID для API).
- Полнотекстовый поиск — генерируемая колонка `tsvector` с русской морфологией + GIN-индекс (см. `db/schema.sql`).
- JSONB для payload сообщений, waveform голосовых и системных событий.
- Драйвер `postgresql+asyncpg://`; миграции Alembic; `db/schema.sql` проверяется в CI против моделей.

### 4.2 Real-time протокол (WS)
Одно соединение `/ws?token=...` на клиента. События JSON: `{type, payload, seq}`.
- Сервер → клиент: `message.new`, `message.edited`, `message.deleted`, `reaction.updated`, `chat.updated`, `typing`, `presence`, `read.updated`, `draft.updated`, `poll.updated`.
- Клиент → сервер: `typing`, `read`, `ping`. Отправка сообщений — через REST (идемпотентность по `client_msg_id`), WS только для доставки событий.
- Reconnect с экспоненциальной задержкой; после reconnect — `GET /sync?since=<seq>` для догрузки пропущенного.
- При одном инстансе API события рассылаются in-process; при масштабировании — Redis Pub/Sub (интерфейс `EventBus` абстрагирован с первого дня).

### 4.3 Хранение файлов
`StorageService` с двумя реализациями: `SupabaseStorage` (демо) и `LocalDiskStorage`/`S3Storage-MinIO` (VPS). Загрузка: клиент → API (валидация MIME/размера, антивирус-заглушка) → storage; выдача — подписанные URL с TTL. Превью изображений/видео генерируются на сервере (Pillow/ffmpeg).

### 4.4 Аутентификация
- Вход: e-mail → 6-значный код (TTL 10 мин, 5 попыток) → JWT.
- Access-токен 15 мин (заголовок Authorization), refresh 30 дней (httpOnly Secure cookie, ротация, таблица `sessions` с отзывом).
- Для WS — короткоживущий ticket, полученный по REST (токен не светится в URL логов дольше необходимого).

### 4.5 PWA / iOS
- `vite-plugin-pwa`: precache оболочки, runtime-кэш аватаров/медиа (stale-while-revalidate), offline-страница с последними чатами из IndexedDB.
- Очередь исходящих: сообщения при отсутствии сети складываются в IndexedDB и отправляются при появлении соединения (Background Sync + fallback).
- Push: подписка PushManager после явного жеста пользователя (iOS требование), VAPID; бейдж — Badging API.
- iOS-специфика: `viewport-fit=cover` + `env(safe-area-inset-*)`, `apple-mobile-web-app-status-bar-style`, отключение резинового скролла на корне, апple-touch-иконки 180×180, splash-скрины.

### 4.6 Безопасность
- Секреты только в env; pydantic-settings падает при отсутствии обязательных переменных.
- CORS whitelist, CSP, HSTS (nginx), sanitize markdown-рендера (rehype-sanitize).
- Rate limiting: slowapi (по IP + по пользователю).
- Файлы: Content-Disposition, отдельный поддомен/route для user-content.

## 5. Профиль деплоя (единый для демо и прода, ADR-023)

Демо и прод — **один и тот же Docker Compose стек** на одном VPS; различаются только
машина, домен и (для прода) бэкапы. Пошагово — `docs/03-SETUP-DEPLOY.md`.

| Компонент | Реализация |
|---|---|
| Frontend | статика собирается в контейнере, отдаётся Caddy (тот же origin) |
| API | FastAPI + WebSocket в Docker, **uvicorn --workers 1** (in-process WS + планировщик) |
| БД | PostgreSQL 16 (контейнер `postgres`, том `pg_data`) или внешняя managed по `DATABASE_URL` |
| Файлы | том `uploads` (диск) / MinIO / S3 — через `STORAGE_BACKEND` |
| Redis | не нужен при одном инстансе (`REDIS_URL` пуст → in-process) |
| HTTPS | Caddy — автоматически (Let's Encrypt) |
| Демо → прод | только сменить `DOMAIN` и секреты в `.env`, тот же `docker compose up -d` |

## 6. CI/CD (GitHub Actions)

1. `lint-test`: ruff + mypy + pytest (backend), eslint + tsc + vitest (frontend) — на каждый push.
2. `schema-check`: прогон Alembic-миграций на PostgreSQL 16 в сервис-контейнере; сверка с `db/schema.sql`.
3. Деплой — вручную на VPS (`git pull && docker compose up -d --build`); авто-деплой из
   CI не настроен (единый self-hosted стек, см. `docs/03-SETUP-DEPLOY.md` §4.4).
