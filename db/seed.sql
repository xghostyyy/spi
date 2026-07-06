-- ============================================================
-- SPI Messenger — демо-данные для тестового деплоя.
-- Запуск: psql "$DATABASE_URL" -f db/seed.sql (после db/schema.sql или alembic upgrade head)
-- Идемпотентно: повторный запуск не создаёт дублей (ON CONFLICT DO NOTHING по email/public_id).
--
-- Аккаунты — вымышленные (@demo.spi-2015.ru), под ними НЕЛЬЗЯ войти через обычный
-- email-код (это реальная одноразовая рассылка на реальный inbox — эти адреса никто
-- не читает). Они нужны, чтобы в списке чатов/группе сразу было на что посмотреть при
-- показе демо. Чтобы попробовать переписку "от первого лица" — войдите под своим
-- e-mail (создастся отдельный аккаунт) и добавьте кого-то из этих username в контакты.
-- ============================================================

INSERT INTO users (public_id, email, email_verified, username, display_name, bio, theme, locale, created_at, updated_at) VALUES
  ('01JDEMOUSERALICE00000001', 'alice.demo@demo.spi-2015.ru',   TRUE, 'alice_s',    'Алиса Соколова',  'Люблю котиков и опен-сорс',        'system', 'ru', now() - interval '30 days', now() - interval '1 day'),
  ('01JDEMOUSERBORIS00000002', 'boris.demo@demo.spi-2015.ru',   TRUE, 'boris_k',    'Борис Кузнецов',  'Backend, кофе, велосипед',          'dark',   'ru', now() - interval '29 days', now() - interval '2 days'),
  ('01JDEMOUSERVICTOR00000003', 'victoria.demo@demo.spi-2015.ru', TRUE, 'victoria_o', 'Виктория Орлова', 'Дизайн и котики (тоже)',           'light',  'ru', now() - interval '28 days', now() - interval '3 days'),
  ('01JDEMOUSERDMITRY00000004', 'dmitry.demo@demo.spi-2015.ru',  TRUE, 'dmitry_v',   'Дмитрий Волков',  'QA. Нашёл баг — считай, что счастлив', 'system', 'ru', now() - interval '20 days', now() - interval '5 days'),
  ('01JDEMOUSERELENA000000005', 'elena.demo@demo.spi-2015.ru',   TRUE, 'elena_t',    'Елена Титова',    'Продакт-менеджер команды SPI',       'system', 'ru', now() - interval '15 days', now() - interval '4 days')
ON CONFLICT (email) DO NOTHING;

-- ------------------------------------------------------------
-- Контакты
-- ------------------------------------------------------------

INSERT INTO contacts (owner_id, contact_id, created_at)
SELECT a.id, b.id, now() - interval '20 days'
FROM users a, users b
WHERE (a.username, b.username) IN
  (('alice_s', 'boris_k'), ('boris_k', 'alice_s'),
   ('alice_s', 'victoria_o'), ('victoria_o', 'alice_s'),
   ('boris_k', 'dmitry_v'), ('dmitry_v', 'boris_k'))
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Личный чат: alice <-> boris
-- ------------------------------------------------------------

INSERT INTO chats (public_id, type, created_at, updated_at)
VALUES ('01JDEMOCHATALICEBORIS0001', 'direct', now() - interval '10 days', now() - interval '1 hour')
ON CONFLICT (public_id) DO NOTHING;

INSERT INTO chat_members (chat_id, user_id, joined_at)
SELECT c.id, u.id, now() - interval '10 days'
FROM chats c, users u
WHERE c.public_id = '01JDEMOCHATALICEBORIS0001' AND u.username IN ('alice_s', 'boris_k')
ON CONFLICT DO NOTHING;

INSERT INTO messages (public_id, chat_id, sender_id, type, body, created_at)
SELECT v.msg_id, c.id, u.id, 'text', v.body, v.created_at
FROM (VALUES
  ('01JDEMOMSGAB00000000000001', 'boris_k', 'Привет! Видел уже фичу с группами?', now() - interval '10 days'),
  ('01JDEMOMSGAB00000000000002', 'alice_s', 'Да, вчера тестировала — закреп сообщений прямо в чате, удобно', now() - interval '10 days' + interval '2 minutes'),
  ('01JDEMOMSGAB00000000000003', 'boris_k', 'А опросы уже работают?', now() - interval '2 days'),
  ('01JDEMOMSGAB00000000000004', 'alice_s', 'Работают, попробуй в группе команды — там как раз есть один', now() - interval '1 hour')
) AS v(msg_id, sender_username, body, created_at)
JOIN chats c ON c.public_id = '01JDEMOCHATALICEBORIS0001'
JOIN users u ON u.username = v.sender_username
ON CONFLICT (public_id) DO NOTHING;

-- ------------------------------------------------------------
-- Личный чат: alice <-> victoria (с ссылкой — для вкладки "Ссылки" медиа-архива)
-- ------------------------------------------------------------

INSERT INTO chats (public_id, type, created_at, updated_at)
VALUES ('01JDEMOCHATALICEVICTOR002', 'direct', now() - interval '8 days', now() - interval '3 days')
ON CONFLICT (public_id) DO NOTHING;

INSERT INTO chat_members (chat_id, user_id, joined_at)
SELECT c.id, u.id, now() - interval '8 days'
FROM chats c, users u
WHERE c.public_id = '01JDEMOCHATALICEVICTOR002' AND u.username IN ('alice_s', 'victoria_o')
ON CONFLICT DO NOTHING;

INSERT INTO messages (public_id, chat_id, sender_id, type, body, created_at)
SELECT v.msg_id, c.id, u.id, 'text', v.body, v.created_at
FROM (VALUES
  ('01JDEMOMSGAV00000000000001', 'victoria_o', 'Обнови, пожалуйста, макет — залила новую версию: https://figma.com/file/spi-messenger-mockups', now() - interval '8 days'),
  ('01JDEMOMSGAV00000000000002', 'alice_s', 'Посмотрела, тёмная тема отлично выглядит!', now() - interval '3 days')
) AS v(msg_id, sender_username, body, created_at)
JOIN chats c ON c.public_id = '01JDEMOCHATALICEVICTOR002'
JOIN users u ON u.username = v.sender_username
ON CONFLICT (public_id) DO NOTHING;

-- ------------------------------------------------------------
-- Группа "Команда SPI" — все пятеро, alice=owner, boris=admin
-- ------------------------------------------------------------

INSERT INTO chats (public_id, type, title, description, owner_id, created_at, updated_at)
SELECT '01JDEMOCHATTEAMGROUP00003', 'group', 'Команда SPI',
       'Рабочий чат разработки мессенджера', u.id, now() - interval '25 days', now() - interval '30 minutes'
FROM users u WHERE u.username = 'alice_s'
ON CONFLICT (public_id) DO NOTHING;

INSERT INTO chat_members (chat_id, user_id, role, can_delete_messages, can_ban, can_invite, can_pin, can_edit_info, joined_at)
SELECT c.id, u.id,
       CASE u.username WHEN 'alice_s' THEN 'owner'::member_role WHEN 'boris_k' THEN 'admin'::member_role ELSE 'member'::member_role END,
       u.username = 'boris_k', u.username = 'boris_k', TRUE, u.username IN ('alice_s', 'boris_k'), u.username = 'boris_k',
       now() - interval '25 days'
FROM chats c, users u
WHERE c.public_id = '01JDEMOCHATTEAMGROUP00003'
  AND u.username IN ('alice_s', 'boris_k', 'victoria_o', 'dmitry_v', 'elena_t')
ON CONFLICT DO NOTHING;

INSERT INTO messages (public_id, chat_id, sender_id, type, body, created_at)
SELECT v.msg_id, c.id, u.id, 'text', v.body, v.created_at
FROM (VALUES
  ('01JDEMOMSGTG00000000000001', 'elena_t',    'Всем привет! Заводим сюда все рабочие обсуждения по мессенджеру', now() - interval '25 days'),
  ('01JDEMOMSGTG00000000000002', 'dmitry_v',   'Нашёл баг: голосовые не проигрываются на Safari iOS 16.3. На 16.4 всё ок', now() - interval '6 days'),
  ('01JDEMOMSGTG00000000000003', 'boris_k',    'Записал в трекер, посмотрю на неделе', now() - interval '6 days' + interval '10 minutes'),
  ('01JDEMOMSGTG00000000000004', 'victoria_o', 'Обновила иконки для PWA — 192/512 и maskable-варианты', now() - interval '2 days'),
  ('01JDEMOMSGTG00000000000005', 'alice_s',    'Отлично, подключил в манифест', now() - interval '30 minutes')
) AS v(msg_id, sender_username, body, created_at)
JOIN chats c ON c.public_id = '01JDEMOCHATTEAMGROUP00003'
JOIN users u ON u.username = v.sender_username
ON CONFLICT (public_id) DO NOTHING;

-- Закреплённое сообщение (первое приветствие)
INSERT INTO pinned_messages (chat_id, message_id, pinned_by, pinned_at)
SELECT c.id, m.id, u.id, now() - interval '24 days'
FROM chats c
JOIN messages m ON m.chat_id = c.id AND m.public_id = '01JDEMOMSGTG00000000000001'
JOIN users u ON u.username = 'alice_s'
WHERE c.public_id = '01JDEMOCHATTEAMGROUP00003'
ON CONFLICT DO NOTHING;

-- Опрос в группе
INSERT INTO messages (public_id, chat_id, sender_id, type, created_at)
SELECT '01JDEMOMSGTG00000000000006', c.id, u.id, 'poll', now() - interval '1 day'
FROM chats c, users u
WHERE c.public_id = '01JDEMOCHATTEAMGROUP00003' AND u.username = 'elena_t'
ON CONFLICT (public_id) DO NOTHING;

INSERT INTO polls (message_id, question, is_anonymous, multi_choice)
SELECT m.id, 'Когда следующий созвон по фазе 5?', FALSE, FALSE
FROM messages m WHERE m.public_id = '01JDEMOMSGTG00000000000006'
ON CONFLICT (message_id) DO NOTHING;

INSERT INTO poll_options (poll_id, text, position)
SELECT m.id, opt.text, opt.position
FROM messages m,
     (VALUES ('Вторник, 15:00', 0), ('Среда, 11:00', 1), ('Пятница, 16:00', 2)) AS opt(text, position)
WHERE m.public_id = '01JDEMOMSGTG00000000000006'
ON CONFLICT DO NOTHING;

INSERT INTO poll_votes (option_id, user_id, created_at)
SELECT po.id, u.id, now() - interval '20 hours'
FROM poll_options po
JOIN messages m ON m.id = po.poll_id AND m.public_id = '01JDEMOMSGTG00000000000006'
JOIN users u ON u.username IN ('alice_s', 'boris_k', 'dmitry_v')
WHERE po.position = 0 AND u.username IN ('alice_s', 'boris_k')
   OR po.position = 1 AND u.username = 'dmitry_v'
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Saved Messages для alice (заметка себе)
-- ------------------------------------------------------------

INSERT INTO chats (public_id, type, owner_id, created_at, updated_at)
SELECT '01JDEMOCHATALICESAVED0004', 'saved', u.id, now() - interval '25 days', now() - interval '25 days'
FROM users u WHERE u.username = 'alice_s'
ON CONFLICT (public_id) DO NOTHING;

INSERT INTO chat_members (chat_id, user_id, role, joined_at)
SELECT c.id, u.id, 'owner', now() - interval '25 days'
FROM chats c, users u
WHERE c.public_id = '01JDEMOCHATALICESAVED0004' AND u.username = 'alice_s'
ON CONFLICT DO NOTHING;

INSERT INTO messages (public_id, chat_id, sender_id, type, body, created_at)
SELECT '01JDEMOMSGSV00000000000001', c.id, u.id, 'text', 'Не забыть проверить экспорт истории в HTML перед демо', now() - interval '1 day'
FROM chats c, users u
WHERE c.public_id = '01JDEMOCHATALICESAVED0004' AND u.username = 'alice_s'
ON CONFLICT (public_id) DO NOTHING;

-- ============================================================
-- Конец seed-данных.
-- ============================================================
