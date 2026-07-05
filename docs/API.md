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
| `typing` | `chat_id`, `user_id`, `kind: text|voice`, флаг начала/конца |
| `presence` | `user_id`, `online`, `last_seen_at` |
| `read.updated` | `chat_id`, `user_id`, `last_read_message_id` |
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
