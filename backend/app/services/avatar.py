"""Обработка загруженного изображения профиля: авто-кроп в квадрат + resize."""

from __future__ import annotations

import asyncio
import io

from PIL import Image

AVATAR_SIZE = 512
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class InvalidImageError(ValueError):
    pass


def _process(data: bytes) -> bytes:
    try:
        image: Image.Image = Image.open(io.BytesIO(data))
        image.load()  # форсирует декодирование для валидации
    except Exception as exc:
        raise InvalidImageError("Не удалось прочитать изображение") from exc

    image = image.convert("RGB")
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    image = image.crop((left, top, left + side, top + side)).resize(
        (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS
    )

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    return buffer.getvalue()


async def process_avatar(data: bytes) -> bytes:
    """Центрирует и обрезает изображение в квадрат AVATAR_SIZE×AVATAR_SIZE (JPEG)."""
    return await asyncio.to_thread(_process, data)
