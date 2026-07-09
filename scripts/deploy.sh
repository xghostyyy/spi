#!/bin/sh
# Быстрое обновление прод-стека на VPS после git push (см. docs/03-SETUP-DEPLOY.md §4.4).
# Запуск на сервере из корня репозитория: ./scripts/deploy.sh
set -e

git pull
docker compose up -d --build
docker compose logs --tail=30 api
