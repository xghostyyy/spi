# SPI Messenger

Кроссплатформенный веб-мессенджер (PWA, mobile-first). Стек, ТЗ и протоколы — в `docs/`.

## Статус

- **Фаза 0 — Каркас:** готово. Монорепо, дизайн-токены, ui-kit, роутинг, CI (lint-test + schema-check).
- **Фаза 1 — Auth и профиль:** готово. Вход по e-mail-коду, JWT + refresh-сессии, профиль
  (аватар/имя/био/username), контакты по `@username`, блокировки, тема/язык.
- **Фаза 2 — Личные чаты:** готово. Real-time доставка (WS + `/ws-ticket`), статусы ✓/✓✓,
  typing, presence, реакции, reply, edit/delete (у себя/у всех, 48ч), разделители дат.
  Только 1-на-1 чаты — группы в фазе 4 (см. `docs/DECISIONS.md`, ADR-009).
- **Фаза 3+** — в разработке (см. `docs/01-TZ.md`, раздел 4).

Журнал решений — `docs/DECISIONS.md`. API — `docs/API.md` (+ `/docs` Swagger UI бэкенда).

## Быстрый старт (локально)

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows; Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env                           # заполнить DATABASE_URL и т.д.
alembic upgrade head                                 # требует запущенный PostgreSQL 16
uvicorn app.main:app --reload --port 8000

# Frontend (второй терминал)
cd frontend
npm install
npm run dev                                          # http://localhost:5173
```

Деплой (демо и прод) — единый Docker-стек (Caddy + FastAPI + Postgres) на одном VPS,
`docker compose up -d`; пошагово, включая тестовый деплой на VPS в РФ — в
`docs/03-SETUP-DEPLOY.md` (см. также `docs/DECISIONS.md`, ADR-023).

## Проверки

```bash
# Backend
cd backend && ruff check . && ruff format --check . && mypy app && pytest -q

# Frontend
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

Тесты backend, требующие PostgreSQL (auth/contacts/messages), проверяются в CI
(GitHub Actions, сервис-контейнер `postgres:16`) — см. `docs/DECISIONS.md`, ADR-002.
