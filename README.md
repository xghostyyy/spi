# SPI Messenger — стартовый пакет документации

Первичная документация для запуска разработки веб-мессенджера SPI через Claude Code.

## Состав пакета

| Файл | Назначение |
|---|---|
| `PROMPT-CLAUDE-CODE.md` | **Готовый промпт** — скопировать в Claude Code и запустить |
| `docs/01-TZ.md` | Техническое задание: полный функционал, фазы, критерии приёмки |
| `docs/02-ARCHITECTURE.md` | Архитектура: стек, структура, WS-протокол, профили деплоя |
| `docs/03-SETUP-DEPLOY.md` | Инструкция: локальный запуск, демо (Vercel+Render+Supabase), VPS с PostgreSQL |
| `db/schema.sql` | Готовый SQL-скрипт создания БД PostgreSQL 16 |
| `design/mockups/` | **Сюда положить макеты Figma** (desktop.png, mobile.png) — обязательно до запуска |

## Порядок запуска

1. Создать/открыть GitHub-репозиторий, склонировать, положить в него содержимое этого пакета.
2. Добавить макеты в `design/mockups/`.
3. Запустить Claude Code в корне репозитория и вставить промпт из `PROMPT-CLAUDE-CODE.md`.
4. Claude Code работает по фазам 0–5, коммитит и пушит после каждой фазы. Результат фазы 5 — MVP для показа.

## Ключевые решения (кратко)

- **Демо:** фронт на Vercel, FastAPI на Render/Railway (Vercel не держит WebSocket), БД и файлы — Supabase.
- **Прод:** свой VPS, Docker Compose, **PostgreSQL 16** по `db/schema.sql`. БД одна и та же в демо и проде — переезд это `pg_dump`/`pg_restore` + смена `DATABASE_URL`.
- **Mobile-first PWA:** установка на домашний экран iPhone, Web Push (iOS 16.4+), offline-режим.
- Звонки и E2EE — фаза 6 (после MVP), кнопки в UI присутствуют сразу.
