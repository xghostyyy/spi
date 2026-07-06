-- ============================================================
-- SPI Messenger — схема базы данных PostgreSQL 16 (v2.0)
-- Один и тот же диалект для демо (Supabase) и прода (VPS).
-- Запуск: psql -U postgres -f schema.sql
-- ============================================================

-- CREATE DATABASE spi_messenger ENCODING 'UTF8';
-- \c spi_messenger

-- Отдельный пользователь приложения (пароль замените и храните в .env!)
-- CREATE ROLE spi_app LOGIN PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO spi_app;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO spi_app;

-- ------------------------------------------------------------
-- Типы
-- ------------------------------------------------------------

CREATE TYPE theme_pref      AS ENUM ('system','light','dark');
CREATE TYPE privacy_level   AS ENUM ('all','contacts','nobody');
CREATE TYPE file_kind       AS ENUM ('image','video','audio','voice','document','avatar','sticker');
CREATE TYPE chat_type       AS ENUM ('direct','group','saved');
CREATE TYPE member_role     AS ENUM ('owner','admin','member');
CREATE TYPE message_type    AS ENUM ('text','photo','video','audio','voice','document',
                                     'contact','location','album','poll','system');

-- Автообновление updated_at
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$ LANGUAGE plpgsql;

-- ------------------------------------------------------------
-- Пользователи и доступ
-- ------------------------------------------------------------

CREATE TABLE users (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id       CHAR(26)     NOT NULL UNIQUE,            -- ULID для API
    email           VARCHAR(255) NOT NULL UNIQUE,
    email_verified  BOOLEAN      NOT NULL DEFAULT FALSE,
    username        VARCHAR(32)  UNIQUE,                     -- @username, латиница/цифры/_
    display_name    VARCHAR(64)  NOT NULL,
    bio             VARCHAR(255),
    phone           VARCHAR(20),
    avatar_file_id  BIGINT,
    password_hash   VARCHAR(255),                            -- NULL = вход только по коду
    theme           theme_pref    NOT NULL DEFAULT 'system',
    locale          VARCHAR(8)    NOT NULL DEFAULT 'ru',
    privacy_last_seen privacy_level NOT NULL DEFAULT 'all',
    privacy_avatar    privacy_level NOT NULL DEFAULT 'all',
    last_seen_at    TIMESTAMPTZ,
    is_admin        BOOLEAN      NOT NULL DEFAULT FALSE,     -- админ сервера (экспорт данных)
    is_deleted      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_username ON users (username);
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE email_login_codes (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email       VARCHAR(255) NOT NULL,
    code_hash   VARCHAR(255) NOT NULL,                       -- хэш 6-значного кода
    attempts    SMALLINT     NOT NULL DEFAULT 0,
    expires_at  TIMESTAMPTZ  NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_codes_email ON email_login_codes (email, expires_at);

CREATE TABLE sessions (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_hash  VARCHAR(255) NOT NULL,                     -- хэш refresh-токена (ротация)
    device_label  VARCHAR(128),                              -- "iPhone Safari", "Chrome Windows"
    ip            VARCHAR(45),
    expires_at    TIMESTAMPTZ  NOT NULL,
    revoked_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_used_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_sessions_user ON sessions (user_id);

CREATE TABLE contacts (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    alias       VARCHAR(64),                                 -- своё имя контакта ("Папа")
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, contact_id)
);

CREATE TABLE blocked_users (
    owner_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, blocked_id)
);

-- ------------------------------------------------------------
-- Файлы
-- ------------------------------------------------------------

CREATE TABLE files (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id    CHAR(26)     NOT NULL UNIQUE,
    owner_id     BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind         file_kind    NOT NULL,
    storage_key  VARCHAR(512) NOT NULL,                      -- путь в storage
    mime_type    VARCHAR(127) NOT NULL,
    size_bytes   BIGINT       NOT NULL,
    width        INTEGER,
    height       INTEGER,
    duration_ms  INTEGER,                                    -- аудио/видео/voice
    waveform     JSONB,                                      -- волновая форма голосового
    thumb_key    VARCHAR(512),                               -- превью
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    original_name VARCHAR(255)                                -- имя файла у отправителя (документы); добавлена
                                                               -- миграцией 0002 после created_at (ALTER TABLE
                                                               -- всегда добавляет колонку в конец — см. ADR-012)
);

ALTER TABLE users
  ADD CONSTRAINT fk_users_avatar FOREIGN KEY (avatar_file_id) REFERENCES files(id) ON DELETE SET NULL;

-- ------------------------------------------------------------
-- Чаты
-- ------------------------------------------------------------

CREATE TABLE chats (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id      CHAR(26)  NOT NULL UNIQUE,
    type           chat_type NOT NULL,
    title          VARCHAR(128),                             -- для групп
    description    VARCHAR(512),
    avatar_file_id BIGINT REFERENCES files(id) ON DELETE SET NULL,
    owner_id       BIGINT REFERENCES users(id) ON DELETE SET NULL, -- владелец группы / хозяин saved
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_chats_updated BEFORE UPDATE ON chats
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE chat_members (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chat_id     BIGINT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        member_role NOT NULL DEFAULT 'member',
    -- права админа (для role='admin')
    can_delete_messages BOOLEAN NOT NULL DEFAULT FALSE,
    can_ban             BOOLEAN NOT NULL DEFAULT FALSE,
    can_invite          BOOLEAN NOT NULL DEFAULT TRUE,
    can_pin             BOOLEAN NOT NULL DEFAULT FALSE,
    can_edit_info       BOOLEAN NOT NULL DEFAULT FALSE,
    -- персональные настройки чата
    is_pinned    BOOLEAN     NOT NULL DEFAULT FALSE,         -- закреплён в списке чатов
    is_archived  BOOLEAN     NOT NULL DEFAULT FALSE,
    muted_until  TIMESTAMPTZ,                                -- NULL = не заглушен, 'infinity' = навсегда
    last_read_message_id BIGINT,
    joined_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    left_at      TIMESTAMPTZ,
    banned_at    TIMESTAMPTZ,
    UNIQUE (chat_id, user_id)
);
CREATE INDEX idx_members_user ON chat_members (user_id, is_archived, is_pinned);

CREATE TABLE chat_invites (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chat_id     BIGINT   NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    token       CHAR(22) NOT NULL UNIQUE,                    -- для ссылки t.spi/j/<token> и QR
    created_by  BIGINT   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    max_uses    INTEGER,
    used_count  INTEGER  NOT NULL DEFAULT 0,
    expires_at  TIMESTAMPTZ,
    revoked_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- Сообщения
-- ------------------------------------------------------------

CREATE TABLE messages (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id     CHAR(26)     NOT NULL UNIQUE,
    chat_id       BIGINT       NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    sender_id     BIGINT       REFERENCES users(id) ON DELETE SET NULL, -- NULL = системное
    client_msg_id UUID,                                      -- идемпотентность отправки
    type          message_type NOT NULL DEFAULT 'text',
    body          TEXT,                                      -- текст / подпись (Markdown-подмножество)
    reply_to_id   BIGINT REFERENCES messages(id) ON DELETE SET NULL,
    forwarded_from_msg_id  BIGINT,
    forwarded_from_user_id BIGINT,
    -- payload для contact/location/system: {vcard...} / {lat,lng} / {event...}
    payload       JSONB,
    edited_at     TIMESTAMPTZ,
    deleted_for_all_at TIMESTAMPTZ,                          -- мягкое удаление «у всех»
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- полнотекстовый поиск: русская морфология + точные слова
    search_tsv    tsvector GENERATED ALWAYS AS (
                    to_tsvector('russian', coalesce(body, ''))
                  ) STORED,
    -- отложенная отправка: NULL = обычное сообщение; иначе видно только автору,
    -- пока фоновый воркер не проставит scheduled_broadcast_at и не разошлёт всем
    -- (см. ADR-012 — новые колонки дописаны в конец физического порядка, после
    -- search_tsv, т.к. именно туда их поставит ALTER TABLE ADD COLUMN в миграции 0003)
    scheduled_at            TIMESTAMPTZ,
    scheduled_broadcast_at  TIMESTAMPTZ,
    UNIQUE (chat_id, sender_id, client_msg_id)
);
CREATE INDEX idx_messages_chat ON messages (chat_id, id);    -- пагинация истории
CREATE INDEX idx_messages_search ON messages USING GIN (search_tsv);
CREATE INDEX idx_messages_scheduled_pending ON messages (scheduled_at)
  WHERE scheduled_at IS NOT NULL AND scheduled_broadcast_at IS NULL;

CREATE TABLE message_attachments (
    message_id  BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    file_id     BIGINT NOT NULL REFERENCES files(id)    ON DELETE CASCADE,
    position    SMALLINT NOT NULL DEFAULT 0,                 -- порядок в альбоме
    PRIMARY KEY (message_id, file_id)
);

CREATE TABLE message_reactions (
    message_id  BIGINT      NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id     BIGINT      NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    emoji       VARCHAR(16) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (message_id, user_id)                        -- одна реакция от пользователя
);

-- Удаление «у себя»
CREATE TABLE message_hidden (
    message_id  BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    PRIMARY KEY (message_id, user_id)
);

CREATE TABLE pinned_messages (
    chat_id     BIGINT NOT NULL REFERENCES chats(id)    ON DELETE CASCADE,
    message_id  BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    pinned_by   BIGINT NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    pinned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (chat_id, message_id)
);

-- Закладки («Сохранённые», флажок на макете)
CREATE TABLE message_bookmarks (
    user_id     BIGINT NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    message_id  BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, message_id)
);

CREATE TABLE drafts (
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chat_id     BIGINT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    body        TEXT   NOT NULL,
    reply_to_id BIGINT REFERENCES messages(id) ON DELETE SET NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, chat_id)
);
CREATE TRIGGER trg_drafts_updated BEFORE UPDATE ON drafts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ------------------------------------------------------------
-- Опросы
-- ------------------------------------------------------------

CREATE TABLE polls (
    message_id   BIGINT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
    question     VARCHAR(255) NOT NULL,
    is_anonymous BOOLEAN NOT NULL DEFAULT TRUE,
    multi_choice BOOLEAN NOT NULL DEFAULT FALSE,
    closed_at    TIMESTAMPTZ
);

CREATE TABLE poll_options (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    poll_id     BIGINT       NOT NULL REFERENCES polls(message_id) ON DELETE CASCADE,
    text        VARCHAR(128) NOT NULL,
    position    SMALLINT     NOT NULL
);

CREATE TABLE poll_votes (
    option_id   BIGINT NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES users(id)        ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (option_id, user_id)
);

-- ------------------------------------------------------------
-- Push-уведомления
-- ------------------------------------------------------------

CREATE TABLE push_subscriptions (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     BIGINT        NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    session_id  BIGINT        REFERENCES sessions(id) ON DELETE CASCADE,
    endpoint    VARCHAR(1024) NOT NULL,
    p256dh      VARCHAR(255)  NOT NULL,
    auth        VARCHAR(255)  NOT NULL,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (endpoint, user_id)
);

-- ============================================================
-- Конец схемы. Демо-данные — в seed.sql
-- ============================================================
