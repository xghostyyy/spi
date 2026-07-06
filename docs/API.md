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
- `GET /api/v1/search?q=` — глобальный поиск: чаты по имени/`@username` собеседника +
  сообщения (полнотекстовый, `tsvector`/`russian`, по всем своим чатам).
- `GET /api/v1/chats/{id}/messages?q=` — тот же полнотекстовый поиск, но внутри чата
  (комбинируется с курсором `before`/`limit`).
- `POST .../messages` также принимает `forward_from_message_public_id` (пересылка —
  копирует body/вложения/тип, проверяет членство в исходном чате) либо `contact`
  (`{name, phone}`) либо `location` (`{lat, lng}`) — ровно одно из этих трёх взаимоисключающих
  полей вместе с `body`/`file_public_ids`. `MessageOut` содержит `payload` и
  `forwarded_from_user_public_id`.

## Реализовано (Фаза 4, группы — в процессе)

- `POST /api/v1/chats/group` — создание группы (`title`, `description?`, `member_usernames[]`),
  создатель становится `owner`.
- `GET /api/v1/chats/{id}/members` — список участников (роль, права admin-флагов, online).
- `POST /api/v1/chats/{id}/members` — добавление участников по `@username` (нужно `can_invite`);
  ре-приглашение вышедшего восстанавливает его же строку `chat_members` (UNIQUE(chat_id,user_id)).
- `DELETE /api/v1/chats/{id}/members/{user_public_id}` — выход из группы (`self`) либо кик
  (нужно `can_ban`); владельца кикнуть нельзя; владелец не может выйти, пока есть другие участники
  (`400 owner_must_transfer`).
- `PATCH /api/v1/chats/{id}/members/{user_public_id}` — смена роли (`admin`/`member`) и
  admin-флагов (`can_delete_messages`/`can_ban`/`can_invite`/`can_pin`/`can_edit_info`) —
  только `owner`.
- `PATCH /api/v1/chats/{id}/info` — переименование/описание группы (нужно `can_edit_info`).
- Права: `owner` имеет все права неявно; `admin` — по конкретным булевым флагам;
  `member` — никаких админ-прав. Смена роли/прав генерирует системное сообщение
  (`type=system`, `sender_id=NULL`, `payload={event, ...}`), рассылается по WS как обычное.
- `ChatOut` для групп содержит `description`, `member_count`, `my_role`, `mentions_count`
  (непрочитанные упоминания `@username` считаются только для групп).

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
