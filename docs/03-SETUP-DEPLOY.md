# SPI Messenger — установка и деплой (v2.0)

Один и тот же **Docker Compose стек** обслуживает и тестовый (демо) деплой, и
продакшен: **Caddy** (единая точка входа + автоматический HTTPS) отдаёт статику
фронта и проксирует **FastAPI + WebSocket**, рядом — **PostgreSQL 16**. Всё на одном
сервере, запуск — одна команда `docker compose up -d`. Обоснование схемы —
`docs/DECISIONS.md`, **ADR-023**.

```
                 ┌──────────────── один VPS (Ubuntu) ────────────────┐
   браузер ─────▶│ Caddy :443  ── авто-HTTPS (Let's Encrypt)          │
   https / wss   │   /                     → статика фронта (SPA)     │
                 │   /api /ws /media /docs → api:8000 (FastAPI + WS)  │
                 │ postgres:16  (том pg_data)                          │
                 │ тома: uploads (файлы), frontend_dist, caddy_data    │
                 └────────────────────────────────────────────────────┘
```

**Зачем именно так:** приложению нужен долгоживущий процесс (постоянный WebSocket +
фоновый планировщик отложенных сообщений живут в памяти процесса). Один сервер + Caddy
даёт это без ограничений serverless, а один origin избавляет от CORS и от вшивания
адреса бэкенда в билд фронта. HTTPS обязателен: без него не работают PWA-установка,
Web Push, доступ к микрофону/камере в звонках и защищённые cookie.

Оглавление:
1. [Переменные окружения (`.env`)](#1-переменные-окружения-env)
2. [Локальная разработка](#2-локальная-разработка)
3. [Тестовый (демо) деплой на VPS в РФ — пошагово](#3-тестовый-демо-деплой-на-vps-в-рф--пошагово)
4. [Продакшен на собственном VPS](#4-продакшен-на-собственном-vps)
5. [Частые проблемы](#5-частые-проблемы)

---

## 1. Переменные окружения (`.env`)

Все секреты — только в `.env` в корне репозитория (в `.gitignore`, в репозиторий не
попадает). Шаблон со всеми полями и комментариями — `.env.example`; скопируйте и
заполните: `cp .env.example .env`.

Ключевые переменные для деплоя:

| Переменная | Назначение | Пример / примечание |
|---|---|---|
| `DOMAIN` | Домен, на котором Caddy выпускает HTTPS | `demo.spi-2015.ru` (для локального http — `:80`) |
| `ACME_EMAIL` | E-mail для уведомлений Let's Encrypt | необязательно |
| `POSTGRES_PASSWORD` | Пароль Postgres в контейнере | `openssl rand -hex 16` |
| `DATABASE_URL` | Адрес БД | **оставить пустым** — api подключится к postgres из compose |
| `JWT_SECRET` | Подпись JWT | `openssl rand -hex 32` (в prod обязателен) |
| `APP_ENV` | Режим | `prod` на деплое; `dev` локально |
| `SMTP_*`, `MAIL_FROM` | Отправка кодов входа | smtp.bz, домен `spi-2015.ru` (см. §1.1) |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Web Push | `npx web-push generate-vapid-keys` (см. §1.2) |
| `VAPID_SUBJECT` | Контакт владельца для push-сервисов | `mailto:admin@spi-2015.ru` |
| `TENOR_API_KEY` | Поиск GIF (необязательно) | пусто = вкладка GIF скрыта |
| `CORS_ORIGINS`, `FRONTEND_URL` | Домен фронта | при same-origin не критичны, укажите `https://<DOMAIN>` |
| `REDIS_URL` | Оставить пустым | пусто = in-process события/планировщик (1 инстанс) |

Фронтенд в прод-стеке `frontend/.env` **не использует** — `frontend/Dockerfile`
собирает его с пустыми `VITE_API_URL`/`VITE_WS_URL` (same-origin). `frontend/.env`
нужен только для локальной разработки.

### 1.1. SMTP (коды входа) — smtp.bz, домен `spi-2015.ru`

Коды входа отправляются через `smtp.bz` от имени домена `spi-2015.ru`. Приложение к
провайдеру не привязано — `backend/app/services/mail.py` шлёт письма стандартным
`aiosmtplib` (STARTTLS) по значениям `SMTP_*` из `.env`, сменить провайдера = сменить
эти переменные. **Если `SMTP_HOST` пуст — код входа печатается в лог контейнера
(`[DEV] Login code for ...`), письма не уходят** (нормально для локальной проверки).

Заказчик настроил smtp.bz заранее. Для деплоя нужно перенести значения в `.env`:
1. Личный кабинет smtp.bz → раздел SMTP-авторизации → взять `SMTP_USER` и
   `SMTP_PASSWORD` (логин/пароль **для SMTP**, не пароль от кабинета). `SMTP_HOST=smtp.bz`,
   `SMTP_PORT=587` уже в шаблоне.
2. Домен `spi-2015.ru` должен быть подтверждён в кабинете smtp.bz (SPF/DKIM
   TXT-записи в DNS домена) — иначе письма уходят в спам/отклоняются. Это разовая
   настройка DNS `spi-2015.ru`, вне репозитория. **Заказчик это уже сделал.**
3. `MAIL_FROM=noreply@spi-2015.ru` (любой адрес на подтверждённом домене).
4. Проверка после деплоя: `POST /api/v1/auth/request-code` с реальным e-mail — письмо
   должно прийти за секунды. Если нет — первым делом перепроверить `SMTP_USER/PASSWORD`
   и статус домена в кабинете smtp.bz, а не код приложения.

### 1.2. Web Push (VAPID-ключи)

1. Сгенерировать пару локально: `npx web-push generate-vapid-keys` (ничего в проект
   ставить не нужно, `npx` скачает временно).
2. Вставить вывод в `.env`: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
   `VAPID_SUBJECT=mailto:admin@spi-2015.ru`.
3. Фронту отдельная переменная не нужна — он получает публичный ключ в рантайме через
   `GET /api/v1/push/vapid-public-key`.
4. Если ключи пусты — приложение работает как обычно, просто push никому не уходит
   (безопасный дефолт для промежуточных проверок).

---

## 2. Локальная разработка

Требования: Node 20+, Python 3.12+, Docker (для БД).

```bash
git clone <REPO_URL> && cd spi-messenger

# Только инфраструктура (Postgres + Redis + MinIO) в Docker:
docker compose -f docker-compose.dev.yml up -d

# Backend (на хосте, с автоперезагрузкой)
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env                              # DATABASE_URL=...localhost:5432..., APP_ENV=dev
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (второй терминал)
cd frontend
npm install
cp .env.example .env                                   # VITE_API_URL/VITE_WS_URL = localhost
npm run dev                                             # http://localhost:5173
```

Для `.env` (корень) локально: `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/spi_messenger`,
`APP_ENV=dev`. Push/PWA требуют HTTPS — проверяются на демо-деплое (§3), не на `localhost`.

---

## 3. Тестовый (демо) деплой на VPS в РФ — пошагово

Итог этого раздела: рабочий `https://demo.spi-2015.ru`, где заказчики **без вашего
участия 1-3 дня** проверяют весь функционал (чаты, группы, каналы, звонки, секретные
чаты, push, PWA). Провайдер — **Timeweb Cloud** (РФ, ~200-300 ₽/мес, принимает карты
РФ). Архитектура провайдеро-независима — подойдёт любой Ubuntu-VPS (альтернативы в
конце раздела).

Порядок важен: **сначала DNS (§3.2), т.к. записи распространяются не мгновенно, а Caddy
не выпустит HTTPS, пока домен не резолвится в IP сервера.**

### 3.1. Создать сервер на Timeweb Cloud

1. https://timeweb.cloud → зарегистрироваться, пополнить баланс (~300 ₽ хватит на месяц).
2. **Cloud-серверы** → **Создать** →
   - ОС: **Ubuntu 24.04**;
   - Конфигурация: минимальная из «стандартных» — **1-2 vCPU, 2 ГБ RAM, 20-30 ГБ NVMe**
     (этого достаточно для демо; звонки идут P2P между браузерами, сервер их не
     обрабатывает);
   - Регион: РФ (Москва/СПб);
   - Аутентификация: загрузить свой **SSH-ключ** (рекомендуется) либо root-пароль
     (Timeweb пришлёт).
3. Создать. Записать **публичный IP** сервера.
4. Проверить вход: `ssh root@<IP>`.

> Порты 80/443 на Timeweb Cloud по умолчанию открыты. Если включён отдельный firewall
> (сетевой экран) — разрешить входящие TCP **22, 80, 443**.

### 3.2. DNS: A-запись `demo.spi-2015.ru → IP`

В панели управления DNS домена `spi-2015.ru` (там же, где настраивали SMTP) добавить:

| Тип | Имя (host) | Значение | TTL |
|---|---|---|---|
| `A` | `demo` | `<IP сервера>` | 300 (5 мин) |

Проверить распространение (может занять от минут до часа):
```bash
ping demo.spi-2015.ru        # должен отвечать ваш IP
# или: nslookup demo.spi-2015.ru
```
**Не переходить к §3.5 (`up`), пока `demo.spi-2015.ru` не резолвится в нужный IP** —
иначе Let's Encrypt не подтвердит домен и Caddy не получит сертификат.

### 3.3. Установить Docker на сервере

По SSH на сервере:
```bash
apt update && apt install -y docker.io docker-compose-plugin git
systemctl enable --now docker
docker compose version        # проверка, что плагин compose доступен
```

### 3.4. Склонировать репозиторий и заполнить `.env`

```bash
git clone <REPO_URL> /opt/spi && cd /opt/spi
cp .env.example .env
nano .env
```
Заполнить как минимум:
```env
DOMAIN=demo.spi-2015.ru
ACME_EMAIL=admin@spi-2015.ru
APP_ENV=prod
POSTGRES_PASSWORD=<openssl rand -hex 16>
DATABASE_URL=                       # оставить ПУСТЫМ (api возьмёт postgres из compose)
JWT_SECRET=<openssl rand -hex 32>
CORS_ORIGINS=https://demo.spi-2015.ru
FRONTEND_URL=https://demo.spi-2015.ru
# SMTP (из кабинета smtp.bz, см. §1.1):
SMTP_HOST=smtp.bz
SMTP_PORT=587
SMTP_USER=<...>
SMTP_PASSWORD=<...>
MAIL_FROM=noreply@spi-2015.ru
# Web Push (npx web-push generate-vapid-keys, см. §1.2):
VAPID_PUBLIC_KEY=<...>
VAPID_PRIVATE_KEY=<...>
VAPID_SUBJECT=mailto:admin@spi-2015.ru
```
Значения `openssl rand ...` можно сгенерировать прямо на сервере: `openssl rand -hex 32`.

### 3.5. Запустить стек

```bash
docker compose up -d --build
```
Что произойдёт автоматически:
- соберётся образ фронта (`frontend/Dockerfile`) и его `dist` попадёт в том, который
  отдаёт Caddy;
- поднимется Postgres, затем `api` накатит миграции (`alembic upgrade head`) и
  запустит FastAPI + WebSocket (**строго 1 воркер** — так требует in-process
  архитектура, см. ADR-023);
- Caddy получит HTTPS-сертификат Let's Encrypt для `demo.spi-2015.ru` (первый запрос
  может занять 10-30 сек, пока идёт выпуск).

Проверить:
```bash
docker compose ps                       # все сервисы healthy/running; frontend-build — Exited (0), это норма
docker compose logs -f caddy            # строки про выданный сертификат
docker compose logs -f api              # 'Application startup complete'
curl https://demo.spi-2015.ru/healthz   # {"status":"ok",...}
```
Открыть в браузере `https://demo.spi-2015.ru` — должно работать по HTTPS.

### 3.6. (Опционально) наполнить демо-данными

`db/seed.sql` создаёт 5 вымышленных пользователей, личные и групповой чаты, опрос,
закреп (под эти аккаунты нельзя войти по коду — они только для наглядности). Скрипт
идемпотентен, безопасно запускать повторно:
```bash
docker compose exec -T postgres psql -U postgres -d spi_messenger < db/seed.sql
```

### 3.7. Финальная проверка функционала

1. Зарегистрироваться по реальному e-mail (код придёт письмом; если письма нет —
   `docker compose logs api | grep -i code`, при пустом SMTP код печатается в лог).
2. Со второго устройства/браузера — второй аккаунт; проверить личный чат в реальном
   времени (доставка, typing, ✓/✓✓, реакции, reply, edit/delete).
3. Группа, канал (пост может только владелец/админ), секретный чат (шифрование),
   отложенное сообщение, папки, стикеры/GIF.
4. Звонок (нужны два устройства с разрешённым микрофоном/камерой; звонки идут
   напрямую между браузерами через STUN — за строгим NAT без TURN могут не соединиться,
   это ожидаемое ограничение, см. ADR-020).
5. **PWA + Push (iPhone):** Safari → Поделиться → «На экран „Домой“» → запустить с
   домашнего экрана → включить уведомления → отправить сообщение со второго устройства
   при закрытом приложении → push должен прийти.

### 3.8. Оставить заказчику на 1-3 дня без присмотра

- Стек самоподдерживающийся: у всех сервисов `restart: unless-stopped` — переживут
  перезагрузку сервера и падения контейнеров.
- Данные (БД) и загруженные файлы — на постоянных томах (`pg_data`, `uploads`),
  редеплой/рестарт их не теряет.
- Логи при жалобах: `docker compose logs --tail=200 api` (или `caddy`).
- Сертификат Caddy продлевает сам. SMTP/VAPID заданы — письма и push работают без вас.
- Стоимость: сервер тарифицируется, пока существует; после демо удалить сервер в
  панели Timeweb, чтобы не платить.

### Альтернативы Timeweb (тот же стек, другой Ubuntu-VPS)

- **Yandex Cloud** (Compute Cloud) — РФ, есть стартовый грант; больше настройки в
  консоли (биллинг-аккаунт, сеть, публичный IP). Дальше — те же §3.3-3.8.
- **Beget** (облачный VPS) — РФ, дёшево и просто, аналогично Timeweb.
- Любой другой Ubuntu 22.04+/24.04 VPS: шаги §3.3-3.8 идентичны, меняется только
  провайдер и способ добавления DNS-записи.

---

## 4. Продакшен на собственном VPS

Тот же стек, что и демо (§3) — отличается только машиной, доменом и обязательными
бэкапами. Требования: Ubuntu 22.04+, домен заказчика, указывающий на IP VPS.

### 4.1. Развернуть
Повторить §3.3-3.5 на прод-VPS со своим `DOMAIN` (напр. `spi.<домен-заказчика>`) и
свежими секретами (`JWT_SECRET`, `POSTGRES_PASSWORD` — **не переиспользовать демо-**).

### 4.2. Перенос данных с демо (если нужно сохранить переписку демо)
```bash
# на демо-сервере:
docker compose exec -T postgres pg_dump -U postgres -Fc spi_messenger > demo.dump
docker compose cp api:/data/uploads ./uploads-demo     # файлы
# перенести demo.dump и uploads-demo на прод (scp), затем на проде:
docker compose exec -T postgres pg_restore -U postgres -d spi_messenger --clean demo.dump
docker compose cp ./uploads-demo/. api:/data/uploads/
```
Чаще для прода начинают с чистой БД — тогда этот шаг пропускается.

### 4.3. Бэкапы (обязательно для прода)
БД и файлы живут на диске VPS — настроить регулярный бэкап:
```bash
# /etc/cron.daily/spi-backup  (chmod +x), пример:
#!/bin/sh
cd /opt/spi
docker compose exec -T postgres pg_dump -U postgres -Fc spi_messenger > /var/backups/spi-$(date +%F).dump
tar czf /var/backups/spi-uploads-$(date +%F).tgz -C /var/lib/docker/volumes/spi-messenger_uploads/_data .
find /var/backups -name 'spi-*' -mtime +14 -delete
```
Копии периодически выгружать за пределы VPS (S3-совместимое хранилище / другой сервер).

### 4.4. Обновление версии

Локально: правите код → проверяете (`npm run dev` / `uvicorn --reload`) → `git push`.
На сервере — подтянуть и пересобрать:
```bash
cd /opt/spi
git pull
docker compose up -d --build      # пересборка изменившихся образов; api сам накатит новые миграции
docker compose logs -f api        # проверить, что миграции прошли и старт успешен
```
Готовая обёртка над этими же командами — `./scripts/deploy.sh` (запускать из `/opt/spi`).
БД и загруженные файлы не трогаются (отдельные тома), пересобираются/перезапускаются
только контейнеры `frontend-build`/`api`/`caddy`.

### 4.5. (Опционально) вынести Postgres в managed-БД
Код к этому готов: задать внешний `DATABASE_URL` в `.env` (напр. Yandex Managed
PostgreSQL) — `api` подключится к нему, сервис `postgres` из compose можно не
запускать (`docker compose up -d --scale postgres=0` или убрать из override).
Так БД получает бэкапы и обслуживание на стороне провайдера. Для одного узла это
избыточно; актуально при росте.

---

## 5. Частые проблемы

| Симптом | Причина / решение |
|---|---|
| Caddy не выдаёт HTTPS, в логах `caddy` ошибки ACME | `DOMAIN` ещё не резолвится в IP сервера (§3.2) или закрыт порт 80/443. Дождаться DNS, открыть порты, `docker compose restart caddy` |
| `502 Bad Gateway` на `/api/*` | `api` ещё стартует/упал. `docker compose logs api` — частая причина: не задан `JWT_SECRET` при `APP_ENV=prod` (падает на старте) |
| `api` перезапускается по кругу | Проверить `DATABASE_URL` (для compose — **пустой**, тогда берётся postgres из стека) и что `POSTGRES_PASSWORD` задан; смотреть `docker compose logs api` |
| Сообщения/typing/presence не в реальном времени | Убедиться, что `api` в **один воркер** (так в `backend/Dockerfile`); WSS проходит через Caddy на `/ws`; в браузере DevTools → Network → WS должен быть `101 Switching Protocols` |
| Отложенные сообщения приходят дважды | Запущено >1 инстанса/воркера api — нарушение архитектуры (ADR-018/023). Держать строго 1 воркер, не масштабировать api без Redis Pub/Sub |
| Загруженные файлы/аватары пропали после рестарта | Проверить, что том `uploads` смонтирован (в новом стеке — да) и `STORAGE_BACKEND=local`, `STORAGE_LOCAL_PATH=/data/uploads` |
| Код входа на e-mail не приходит | `SMTP_USER/PASSWORD` из кабинета smtp.bz и статус домена `spi-2015.ru` (SPF/DKIM), см. §1.1; при пустом `SMTP_HOST` код только в логе `api` |
| Push не приходит вообще | Пусты `VAPID_PUBLIC_KEY/PRIVATE_KEY` — отправка тихо пропускается (§1.2) |
| Push не приходит на iPhone | PWA не установлена на домашний экран, iOS < 16.4, либо подписка запрошена не по жесту пользователя. Только через HTTPS |
| Звонок не соединяется у части пользователей | Строгий/симметричный NAT без TURN — известное ограничение (только публичный STUN, ADR-020) |
| Оплата/доступ к зарубежному сервису из РФ | Использовать РФ-провайдера (Timeweb/Yandex/Beget) — на них весь стек ставится одинаково |
| iOS: контент под «чёлкой» | `viewport-fit=cover` + `env(safe-area-inset-*)` (уже в вёрстке) |
