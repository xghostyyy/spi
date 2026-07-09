"""Конфигурация приложения.

Все секреты приходят из переменных окружения (.env в корне монорепо).
В dev-режиме (APP_ENV=dev) обязательные секреты имеют безопасные заглушки,
чтобы проект запускался локально без единого внешнего ключа; в prod
отсутствие секретов — фатальная ошибка при старте.
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "dev-secret-not-for-production"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["dev", "prod"] = "dev"

    # --- База данных ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/spi_messenger"

    # --- Безопасность ---
    jwt_secret: str = ""
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 30

    # --- Хранилище файлов ---
    storage_backend: Literal["supabase", "local", "s3"] = "local"
    supabase_url: str = ""
    supabase_service_key: str = ""
    storage_local_path: str = "./data/uploads"
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "spi-media"

    # --- Почта (пусто в dev = код входа пишется в лог) ---
    # smtp_api_key — приоритетный способ (HTTP API поставщика письма, порт 443);
    # smtp_host/user/password — сырой SMTP (fallback для локальной разработки или
    # провайдеров без HTTP API). См. ADR-024: у многих VPS исходящий SMTP (587/465)
    # заблокирован по умолчанию, а исходящий HTTPS — почти никогда.
    smtp_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "noreply@spi-messenger.ru"

    # --- Web Push ---
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@spi-messenger.ru"

    # --- Поиск GIF (Tenor). Пусто = поиск отключён (см. GET /gifs/enabled) ---
    tenor_api_key: str = ""

    # --- Прочее ---
    cors_origins: str = "http://localhost:5173"
    redis_url: str = ""
    frontend_url: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _apply_dev_fallbacks_or_fail(self) -> Self:
        if not self.jwt_secret:
            if self.app_env == "prod":
                msg = "JWT_SECRET is required in prod (generate: openssl rand -hex 32)"
                raise ValueError(msg)
            self.jwt_secret = _DEV_JWT_SECRET
        if self.app_env == "prod" and self.jwt_secret == _DEV_JWT_SECRET:
            msg = "JWT_SECRET must not use the dev fallback value in prod"
            raise ValueError(msg)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
