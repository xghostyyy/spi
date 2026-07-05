# SPI Messenger — API

## REST

Полная спецификация REST-эндпоинтов генерируется автоматически (FastAPI / OpenAPI):

- **Swagger UI:** `GET /docs`
- **OpenAPI JSON:** `GET /openapi.json`

Базовый префикс — `/api/v1`. Аутентификация — `Authorization: Bearer <access>`;
refresh-токен — httpOnly cookie `spi_refresh` (ротация на каждом обновлении).

| Группа | Префикс | Назначение |
|---|---|---|
| Health | `/healthz` | Проверка живости (без префикса api) |
| Auth | `/api/v1/auth` | Запрос кода на e-mail, вход по коду, refresh, logout, сессии |
| Users | `/api/v1/users` | Профиль, username, настройки, приватность, блокировки |
| Contacts | `/api/v1/contacts` | Контакты по @username |
| Chats | `/api/v1/chats` | Список чатов, создание, закреп/архив/mute, участники |
| Messages | `/api/v1/chats/{id}/messages` | История, отправка (идемпотентность по `client_msg_id`), edit/delete, реакции |
| Files | `/api/v1/files` | Загрузка, подписанные URL |
| Search | `/api/v1/search` | Глобальный поиск и поиск по чату |
| Push | `/api/v1/push` | Подписки Web Push |
| Sync | `/api/v1/sync?since=<seq>` | Догрузка событий после reconnect |

*(Таблица пополняется по мере реализации фаз; актуальный источник истины — `/openapi.json`.)*

## Реализовано (Фаза 1)

- `POST /api/v1/auth/request-code` — код на e-mail (в dev — только в лог сервера).
- `POST /api/v1/auth/verify-code` — код → `access_token` (в теле) + `spi_refresh` (httpOnly cookie).
- `POST /api/v1/auth/refresh` — по cookie выдаёт новый `access_token` и ротирует cookie.
- `POST /api/v1/auth/logout` — отзывает текущую сессию, чистит cookie.
- `GET/PATCH /api/v1/users/me` — профиль; `GET /api/v1/users/check-username` — проверка занятости.
- `POST /api/v1/users/me/avatar` — загрузка аватара (multipart), сервер авто-кропит в квадрат 512×512.
- `GET/POST /api/v1/contacts`, `DELETE /api/v1/contacts/{public_id}` — контакты по `@username`,
  добавление идемпотентно (`INSERT ... ON CONFLICT`).
- `GET/POST /api/v1/blocks`, `DELETE /api/v1/blocks/{public_id}` — чёрный список.

Формат ошибок: `{"code": "snake_case_reason", "message": "текст для пользователя"}`
с соответствующим HTTP-статусом (400/401/403/404/409).

## Реализовано (Фаза 2, только личные чаты)

- `GET/POST /api/v1/chats`, `PATCH /api/v1/chats/{public_id}` — список (превью, unread,
  pin/archive/mute), создание direct-чата по `@username`.
- `GET/POST /api/v1/chats/{public_id}/messages` — история (курсор `before`, `limit≤100`),
  отправка (идемпотентно по `client_msg_id`).
- `PATCH/DELETE /api/v1/chats/{public_id}/messages/{message_public_id}` — правка,
  удаление (`scope=self|all`, `all` — только автор, окно 48ч).
- `POST .../messages/{message_public_id}/reactions` — тоггл реакции (одна на пользователя).
- `POST /api/v1/auth/ws-ticket` → `GET /ws?ticket=...` — WS-подключение; `GET
  /api/v1/sync?since=<ISO-время>` — упрощённая догрузка сообщений после reconnect
  (см. `docs/DECISIONS.md`, ADR-008: без персистентного event-log).
- Группы, поиск, черновики (drafts) и опросы — ещё не реализованы (см. `docs/01-TZ.md`).

## Реализовано (Фаза 3, медиа)

- `POST /api/v1/files` (multipart: `file`, `kind`, опционально `duration_ms`/`waveform`) —
  загрузка фото (авто-resize ≤2000px + превью 480px), видео/аудио/документов (как есть),
  голосовых (клиент шлёт волновую форму и длительность — сервер аудио не декодирует,
  см. `docs/DECISIONS.md`). MIME/размер валидируются по `kind` (лимиты 15–100 МБ).
- `POST /api/v1/chats/{id}/messages` принимает `file_public_ids` (до 10); тип сообщения
  (`photo`/`video`/`audio`/`voice`/`document`/`album`) выводится из вложений автоматически.
  Нужен либо `body`, либо хотя бы одно вложение (иначе `400 empty_message`).
- Ответ сообщения включает `attachments: FileOut[]` (`url`, `thumb_url`, `width`/`height`,
  `duration_ms`, `waveform`, `original_name`).
- `GET /api/v1/chats/saved` — идемпотентно находит/создаёт личный чат `type=saved`
  (Saved Messages); отправка/чтение — через обычные `.../messages` эндпоинты.
- `GET /api/v1/bookmarks`, `POST /api/v1/bookmarks/{message_public_id}` — закладки
  (флажок) на любое сообщение из своих чатов, независимо от Saved Messages; `MessageOut`
  содержит `bookmarked`.
- vCard/геолокация, поиск, пересылка — в разработке (см. `docs/01-TZ.md`).

## WebSocket `/ws`

Одно соединение на клиента. Подключение: короткоживущий ticket, полученный по REST
(`POST /api/v1/auth/ws-ticket`), передаётся как `/ws?ticket=...`.

Формат события: `{"type": string, "payload": object, "seq": number}` — `seq` монотонно
растёт в рамках пользователя; после reconnect клиент вызывает `GET /api/v1/sync?since=<seq>`.

### Сервер → клиент

| type | payload (кратко) |
|---|---|
| `message.new` | сообщение целиком + `chat_id` |
| `message.edited` | `message_id`, новое `body`, `edited_at` |
| `message.deleted` | `message_id`, `chat_id`, scope: `all` |
| `reaction.updated` | `message_id`, агрегированные реакции |
| `chat.updated` | изменённые поля чата / членства |
| `typing` | `chat_id`, `user_public_id`, `kind: text|voice`, флаг начала/конца |
| `presence` | `user_public_id`, `online`, `last_seen_at` |
| `read.updated` | `chat_id`, `user_public_id`, `last_read_message_id` |
| `draft.updated` | `chat_id`, `body`, `reply_to_id` |
| `poll.updated` | `message_id`, агрегированные голоса |

### Клиент → сервер

| type | payload |
|---|---|
| `typing` | `chat_id`, `kind: text|voice`, `active: bool` |
| `read` | `chat_id`, `message_id` |
| `ping` | — (keep-alive; сервер отвечает `pong`) |

Отправка сообщений — **только через REST** (`POST .../messages` с `client_msg_id`),
WS используется исключительно для доставки событий.
