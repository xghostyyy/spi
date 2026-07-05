"""Обработка загружаемых изображений для медиа-сообщений (фото)."""

from __future__ import annotations

import asyncio
import io

from PIL import Image

MAX_DIMENSION = 2000
THUMB_DIMENSION = 480


class InvalidMediaError(ValueError):
    pass


def _process_image(data: bytes) -> tuple[bytes, bytes, int, int]:
    try:
        image: Image.Image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise InvalidMediaError("Не удалось прочитать изображение") from exc

    image = image.convert("RGB")
    width, height = image.size

    if max(width, height) > MAX_DIMENSION:
        ratio = MAX_DIMENSION / max(width, height)
        image = image.resize(
            (round(width * ratio), round(height * ratio)), Image.Resampling.LANCZOS
        )
        width, height = image.size

    main_buffer = io.BytesIO()
    image.save(main_buffer, format="JPEG", quality=90)

    thumb = image.copy()
    thumb.thumbnail((THUMB_DIMENSION, THUMB_DIMENSION), Image.Resampling.LANCZOS)
    thumb_buffer = io.BytesIO()
    thumb.save(thumb_buffer, format="JPEG", quality=80)

    return main_buffer.getvalue(), thumb_buffer.getvalue(), width, height


async def process_image(data: bytes) -> tuple[bytes, bytes, int, int]:
    """Возвращает (изображение, превью, ширина, высота); уменьшает до MAX_DIMENSION."""
    return await asyncio.to_thread(_process_image, data)
