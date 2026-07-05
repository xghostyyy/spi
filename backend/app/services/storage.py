"""Абстракция хранилища файлов: локальный диск (dev/VPS) или Supabase Storage (демо)."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def public_url(self, key: str) -> str:
        """Путь, по которому файл отдаётся. Относительный — фронт добавляет VITE_API_URL."""


class LocalDiskStorage(StorageBackend):
    def __init__(self, root: str) -> None:
        self._root = Path(root)

    async def save(self, key: str, data: bytes) -> None:
        path = self._root / key

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(_write)

    def public_url(self, key: str) -> str:
        return f"/media/{key}"


class SupabaseStorage(StorageBackend):
    """Реализация под Supabase Storage — подключается при настройке демо-окружения."""

    async def save(self, key: str, data: bytes) -> None:
        raise NotImplementedError("SupabaseStorage ещё не подключен (см. docs/DECISIONS.md)")

    def public_url(self, key: str) -> str:
        raise NotImplementedError("SupabaseStorage ещё не подключен (см. docs/DECISIONS.md)")


def get_storage() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalDiskStorage(settings.storage_local_path)
    if settings.storage_backend == "supabase":
        return SupabaseStorage()
    raise NotImplementedError(f"Storage backend {settings.storage_backend!r} ещё не реализован")
