# Сборка статики фронтенда для прод-стека (см. docker-compose.yml, ADR-023).
# Образ используется сервисом frontend-build: собирает dist и кладёт его в общий
# том, который отдаёт Caddy. Само приложение внутри контейнера не запускается.
#
# VITE_API_URL / VITE_WS_URL пусты → фронт ходит по относительным путям того же
# origin (Caddy), без CORS и без вшитого в билд адреса бэкенда (см. src/shared/api
# и src/shared/ws/client.ts). Для split-origin деплоя задайте их непустыми.
FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ENV VITE_API_URL="" \
    VITE_WS_URL=""
RUN npm run build

# Готовая статика — в /app/dist. Копируется в том через command в compose.
