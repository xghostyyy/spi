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
| БД | **PostgreSQL 16 везде** (Supabase в демо, контейнер на VPS) | Один диалект демо=прод, русский полнотекстовый поиск, JSONB; переезд = `pg_dump`/`pg_restore` |
| Файлы | Supabase Storage (демо) / локальный диск или MinIO (VPS) | Абстракция StorageService |
| Push | Web Push (pywebpush, VAPID) | Работает на iOS PWA 16.4+ |
| Почта | SMTP (aiosmtplib) / Resend API | Коды входа |
| Кэш/PubSub | Redis (опционально в MVP; обязателен при >1 инстанса API) | Fan-out WS-событий |
| Деплой демо | Vercel (front) + Render/Railway (API) + Supabase (БД+Storage) | Бесплатный публичный URL |
| Деплой prod | VPS: Docker Compose (nginx + api + postgres + redis + certbot) | Полный контроль |

> **Почему API не на Vercel:** Vercel Serverless не держит постоянные WebSocket-соединения — мессенджеру нужен long-lived процесс. Поэтому FastAPI живёт на Render/Railway (демо) или VPS (prod), а Vercel раздаёт только статику фронта.

## 2. Схема системы

```
                    ┌─────────────────────────────┐
   iPhone PWA ────┐ │  Frontend (React SPA/PWA)   │
   Android PWA ───┼─►  Vercel (демо) / nginx (VPS)│
   Desktop Web ───┘ └───────────┬─────────────────┘
                        HTTPS   │   WSS
                    ┌───────────▼─────────────────┐
                    │  FastAPI (REST + WebSocket) │
                    │  Render/Railway (демо)      │
                    │  Docker на VPS (prod)       │
                    └───┬─────────┬─────────┬─────┘
                        │         │         │
                  ┌─────▼────┐ ┌──▼─────┐ ┌─▼───────────┐
                  │ БД       │ │ Redis  │ │ Storage     │
                  │ Postgres │ │(pubsub)│ │ Supabase/   │
                  │ 16       │ │        │ │ MinIO/диск  │
                  └──────────┘ └────────┘ └─────────────┘
                        + SMTP (коды входа) + Web Push (VAPID)
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

## 5. Два профиля деплоя

| | Демо (быстрый показ) | Продакшен (VPS) |
|---|---|---|
| Frontend | Vercel (авто-деплой из GitHub) | nginx (статика) |
| API | Render / Railway (Docker) | Docker Compose, systemd |
| БД | Supabase PostgreSQL | PostgreSQL 16 (контейнер или managed) |
| Файлы | Supabase Storage | MinIO / локальный том |
| Redis | не обязателен | контейнер redis |
| HTTPS | автоматически | certbot / Caddy |
| Переключение | — | только `DATABASE_URL`, `STORAGE_*` в `.env` |

## 6. CI/CD (GitHub Actions)

1. `lint-test`: ruff + mypy + pytest (backend), eslint + tsc + vitest (frontend) — на каждый push.
2. `schema-check`: прогон Alembic-миграций на PostgreSQL 16 в сервис-контейнере; сверка с `db/schema.sql`.
3. `deploy-demo`: push в `main` → Vercel деплоит фронт автоматически; Render — по deploy hook.
