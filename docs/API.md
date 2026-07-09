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
- `POST /api/v1/chats/{id}/invites` — создать пригласительную ссылку (нужен `can_invite`);
  `max_uses?`, `expires_in_hours?`; токен — 22 URL-safe символа под `t.spi/join/<token>`
  (фронтенд-роут `/join/:token`, компонент рендерит QR через `qrcode`).
  `GET .../invites` — список ссылок, `DELETE .../invites/{token}` — отзыв.
- `GET /api/v1/invites/{token}` — публичный превью (без авторизации): название/описание/
  число участников группы + `valid` (не отозвана, не истекла, не исчерпан лимит).
- `POST /api/v1/invites/{token}/join` — вступление по ссылке (нужна авторизация); повторно
  приглашённый вышедший участник реактивирует свою же строку `chat_members`; для
  забаненного (`banned_at` не NULL) — `403 banned_from_chat`.
- `GET /api/v1/chats/{id}/pinned` — список закреплённых сообщений группы (новые сверху).
  `POST/DELETE /api/v1/chats/{id}/messages/{message_id}/pin` — закрепить/открепить
  (нужен `can_pin`; только для групп — `400 not_a_group` для direct/saved). Оба действия
  рассылают `pinned.updated` по WS и создают системное сообщение `message_pinned`.
- `GET /api/v1/auth/sessions` — активные сессии текущего пользователя (`revoked_at IS NULL`
  и не истекла), с `is_current` (определяется по `session_id` из httpOnly `spi_refresh`
  куки текущего запроса, а не из access-токена — он не привязан к сессии). `DELETE
  /api/v1/auth/sessions/{id}` — отозвать сессию (только свою — 404, если чужая); если
  отзывается сессия текущего браузера, заодно чистится `spi_refresh` cookie.
- `GET /api/v1/chats/{id}/export?format=json|html` — выгрузка полной истории чата
  (владелец аккаунта — свои чаты; полный серверный экспорт для администратора не
  реализован, см. ТЗ §2.6 — вне текущего объёма MVP). `json` — структурированный
  `{chat, exported_at, exported_by, messages: MessageOut[]}`; `html` — самодостаточная
  HTML-страница (без внешних ресурсов) с транскриптом. Оба варианта отдаются с
  `Content-Disposition: attachment`, то есть браузер сразу скачивает файл.
- `POST .../messages` также принимает `poll: {question, options[2..10], is_anonymous?,
  multi_choice?}` — создаёт `type=poll` сообщение с таблицами `polls`/`poll_options`.
  Опрос нельзя переслать (`400 cannot_forward_poll`). `MessageOut.poll` содержит вопрос,
  флаги, `closed_at`, `total_votes` и список опций (`position`, `text`, `votes`,
  `voted_by_me`) — позиция (`position`), а не внутренний ID, используется как идентификатор
  варианта в API, чтобы не светить сырые PK.
- `GET /api/v1/chats/{id}/media?tab=media|files|voice|links` — медиа-архив чата (доступен
  для любого типа чата, не только групп): `media` — фото/видео/альбомы, `files` —
  документы, `voice` — голосовые и аудио, `links` — сообщения, где `body` содержит
  `http(s)://` (регэксп по `body`, не полнотекстовый поиск). Возвращает `MessageOut[]`,
  новые последними, `limit` по умолчанию 100 (макс. 200).
- `POST .../messages/{id}/poll/vote` — `{option_positions: number[]}`; для не-`multi_choice`
  опроса допустима ровно одна позиция (иначе `400 single_choice_only`); повторное
  голосование заменяет предыдущий выбор, а не добавляет к нему. `POST .../poll/close` —
  закрыть опрос досрочно (только автор сообщения, иначе `403`). Оба рассылают
  `poll.updated` (payload — `MessageOut` целиком, как и `reaction.updated`).

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
| `pinned.updated` | `chat_public_id`, `pinned: MessageOut[]` (полный список закреплённых) |

### Клиент → сервер

| type | payload |
|---|---|
| `typing` | `chat_id`, `kind: text|voice`, `active: bool` |
| `read` | `chat_id`, `message_id` |
| `ping` | — (keep-alive; сервер отвечает `pong`) |

Отправка сообщений — **только через REST** (`POST .../messages` с `client_msg_id`),
WS используется исключительно для доставки событий.

### Сигналинг звонков (Фаза 6, WebRTC 1-на-1)

Пять типов событий, каждое — **слепой relay**: клиент отправляет с `chat_id` (личный
чат) и `call_id` (генерируется звонящим), сервер резолвит второго участника чата и
пересылает payload как есть, добавив `from_public_id`. Состояние звонка сервер не
хранит (см. ADR-020) — все пять одинаково идут и как "клиент → сервер", и как
"сервер → клиент" (тому же типу, для второй стороны).

| type | payload |
|---|---|
| `call.invite` | `chat_id`, `call_id`, `kind: audio|video`, `sdp` (offer), `caller_display_name?`, `caller_avatar_url?` |
| `call.answer` | `chat_id`, `call_id`, `sdp` (answer) |
| `call.ice-candidate` | `chat_id`, `call_id`, `candidate` |
| `call.decline` | `chat_id`, `call_id`, `reason: declined|busy` |
| `call.hangup` | `chat_id`, `call_id` |

ICE — только публичный STUN (`stun:stun.l.google.com:19302`), TURN не настроен (см.
ADR-020) — звонок может не установиться через строгий NAT/файрвол на одной из сторон.

После звонка звонящая сторона пишет обычное сообщение `POST .../messages` с полем
`call: {kind, outcome, duration_seconds?}` (`outcome: answered|missed|declined|canceled`)
— это лог звонка в истории чата, а не часть сигналинга.

## Реализовано (Фаза 5, Web Push)

- `GET /api/v1/push/vapid-public-key` — публичный VAPID-ключ (без авторизации) для
  `PushManager.subscribe({applicationServerKey: ...})` на фронтенде.
- `POST /api/v1/push/subscribe` — сохранить/обновить подписку браузера (`endpoint`,
  `keys.p256dh`, `keys.auth` — стандартный `PushSubscription.toJSON()`); идемпотентно
  (`ON CONFLICT` по `(endpoint, user_id)`).
- `POST /api/v1/push/unsubscribe` — удалить подписку по `endpoint`.
- Отправка: при `POST .../messages` сервер шлёт push всем офлайн-участникам чата (кроме
  автора и тех, у кого чат заглушен `muted_until`) через `notify_chat_members()`
  (`app/services/push.py`), используя `pywebpush` + `VAPID_PRIVATE_KEY`/`VAPID_PUBLIC_KEY`
  из окружения. «Офлайн» определяется по `ConnectionManager.is_online()` — то есть push не
  дублирует WS-уведомление тем, у кого открыто соединение. Если VAPID-ключи не заданы
  (пусто в `.env`) — отправка молча пропускается, ошибка не бросается (см. ADR — будет
  дополнено при полной реализации Web Push на фронтенде).
- Протухшие подписки (браузер вернул `404`/`410 Gone`) удаляются из `push_subscriptions`
  автоматически при следующей попытке отправки.

## Реализовано (Фаза 6, отложенная отправка)

- `POST .../messages` принимает `scheduled_at` (ISO-datetime, строго в будущем —
  иначе `400 scheduled_at_in_past`). Такое сообщение сразу создаётся в БД, но не
  рассылается по WS/push и не видно в обычной истории (`GET .../messages`) никому,
  включая автора, пока не наступит время.
- `GET .../messages/scheduled` — список ожидающих отправки сообщений автора в этом чате.
- `PATCH .../messages/scheduled/{id}` — перенести время (`scheduled_at`, снова строго
  в будущем). `DELETE .../messages/scheduled/{id}` — отменить (жёсткое удаление, пока не
  отправлено). Оба — только автор, 404 иначе.
- Доставка — фоновый цикл в процессе API (`app/services/scheduler.py`, поллинг раз в
  `SCHEDULED_POLL_INTERVAL_SECONDS=15` секунд, без внешней очереди/cron — см. ADR-018),
  запускается через FastAPI lifespan при старте приложения. При наступлении срока
  сообщение рассылается по WS (`message.new`) и push — так же, как обычное сообщение,
  просто с отложенным моментом первого появления.

## Реализовано (Фаза 6, папки чатов)

- `GET /api/v1/folders` — папки текущего пользователя, отсортированы по `position`.
- `POST /api/v1/folders` `{name, chat_public_ids?}` — создать папку. `chat_public_ids` —
  список чатов-участников папки; каждый должен быть чатом, в котором пользователь
  состоит (иначе `404 chat_not_found`). Пустое имя — `400 name_required`.
- `PATCH /api/v1/folders/{folder_public_id}` `{name?, chat_public_ids?}` — переименовать
  и/или полностью заменить состав чатов папки (не патч-добавление, а замена списка целиком).
- `DELETE /api/v1/folders/{folder_public_id}` — удалить папку. Обе PATCH/DELETE-ручки —
  только владелец папки, иначе `404 folder_not_found`.
- Папка — чисто пользовательский фильтр поверх общего списка чатов (`GET /chats` не
  меняется); фронтенд сам пересекает `chat_public_ids` папки со списком чатов при выборе
  вкладки. Порядок вкладок фиксируется в момент создания папки (`position` = счётчик
  папок пользователя + 1); перетаскивание/переупорядочивание вкладок не реализовано —
  сочтено избыточным для пост-MVP объёма фазы.

## Реализовано (Фаза 6, стикеры и GIF)

- `POST .../messages` принимает `sticker: {pack, sticker_id, emoji, url}` или
  `gif: {url, preview_url?, width?, height?}` — как и `contact`/`location`, это
  отдельная ветка от обычного текста/вложений: создаёт сообщение с `type = 'sticker'`
  либо `type = 'gif'` и телом `payload` = переданный объект как есть (без файла на
  storage — см. ADR-019).
- `GET /api/v1/gifs/enabled` — `{"enabled": bool}`, признак того, настроен ли
  `TENOR_API_KEY`. Публичный (без авторизации), фронтенд использует его, чтобы скрыть
  вкладку GIF в пикере, если поиск не сконфигурирован.
- `GET /api/v1/gifs/search?q=&limit=` — проксирует Tenor API v2 (`media_filter=gif`),
  отдаёт `[{id, url, preview_url, width, height}]`. Без `TENOR_API_KEY` — пустой список
  (не ошибка). Лимит `30/минуту` на пользователя (`@limiter.limit`) — сторонний API
  тарифицируется по квоте, а не по соображениям безопасности.
- Встроенный набор стикеров — статичные SVG во `frontend/public/stickers/`, каталог в
  `frontend/src/shared/stickers/catalog.ts`; загрузка собственных стикеров пользователем
  не реализована (см. ADR-019).

## Реализовано (Фаза 6, звонки WebRTC 1-на-1)

- Сигналинг (`call.invite`/`call.answer`/`call.ice-candidate`/`call.decline`/`call.hangup`)
  — см. раздел «Сигналинг звонков» выше. Только личные чаты, только STUN (без TURN,
  ADR-020).
- `POST .../messages` принимает `call: {kind: audio|video, outcome: answered|missed|
  declined|canceled, duration_seconds?}` — лог звонка в истории, пишется только звонящей
  стороной после завершения сигналинга (не часть самого сигналинга).

## Реализовано (Фаза 6, секретные чаты — E2EE)

Крипто (ECDH P-256 + AES-GCM, без Double Ratchet) и все ограничения — см. ADR-021.

- `POST /api/v1/users/me/e2ee-key` `{public_key}` — публикует ECDH-публичный ключ
  (base64 SPKI) текущего пользователя. `UserOut`/`ChatOut` теперь содержат
  `e2ee_public_key` и `peer_e2ee_public_key` соответственно.
- `POST /api/v1/chats/secret` `{username}` — создаёт (или возвращает существующий)
  секретный чат с пользователем. Требует ключ у ОБОИХ участников: `400 no_e2ee_key`
  (нет своего) / `400 peer_no_e2ee_key` (нет у собеседника). Отдельная сущность от
  обычного `POST /api/v1/chats` с тем же собеседником — оба могут существовать
  одновременно.
- `POST .../messages` в секретном чате (`chat.is_secret = true`) принимает **только**
  `encrypted: {ciphertext, iv}` (оба — base64). Любое другое поле (`body`,
  `file_public_ids`, `contact`, `location`, `poll`, `sticker`, `gif`, `call`,
  `forward_from_message_public_id`) — `400 secret_chat_text_only`. В обычном чате поле
  `encrypted`, наоборот, запрещено — `400 encrypted_not_allowed`.
- `PATCH .../messages/{id}` (редактирование) в секретном чате — `400 secret_chat_no_edit`.
  Пересылка сообщения ИЗ секретного чата (в любой чат) — `400 cannot_forward_secret`.
- `GET /api/v1/search` полностью исключает секретные чаты — ни по названию/собеседнику,
  ни по содержимому.
- Пуш-уведомление о сообщении в секретном чате всегда показывает фиксированный текст
  «🔒 Зашифрованное сообщение», никогда не производный от содержимого.

## Реализовано (Фаза 6, каналы)

Канал = групповой чат (`type = 'group'`) с `is_channel = true` — переиспользует всю
инфраструктуру групп (участники/роли, инвайты, закреп, медиа-архив, экспорт). Детали
и обоснование — ADR-022.

- `POST /api/v1/chats/channel` `{title, description?}` — создаёт канал, создатель —
  `owner`. Управление подписчиками/ролями/инвайтами — те же ручки, что у групп
  (`.../members`, `.../invites`).
- `POST .../messages` в канале — только `owner`/`admin`; для рядового подписчика —
  `403 channel_read_only`.
- `GET .../members` в канале для рядового подписчика возвращает только `owner`/
  `admin` (список остальных подписчиков скрыт — приватность, как в Telegram);
  `ChatOut.member_count` при этом всегда честное общее число.
