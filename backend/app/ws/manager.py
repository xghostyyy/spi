"""In-process менеджер WS-соединений (EventBus).

При масштабировании на несколько инстансов API заменяется на Redis Pub/Sub
за тем же интерфейсом send_to_user/send_to_users (см. docs/02-ARCHITECTURE.md §4.2).
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._seq: dict[int, int] = defaultdict(int)

    def connect(self, user_id: int, ws: WebSocket) -> None:
        self._connections[user_id].add(ws)

    def disconnect(self, user_id: int, ws: WebSocket) -> None:
        self._connections[user_id].discard(ws)
        if not self._connections[user_id]:
            del self._connections[user_id]

    def is_online(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))

    def _next_seq(self, user_id: int) -> int:
        self._seq[user_id] += 1
        return self._seq[user_id]

    async def send_to_user(self, user_id: int, event_type: str, payload: object) -> None:
        connections = list(self._connections.get(user_id, ()))
        if not connections:
            return
        message = json.dumps(
            {"type": event_type, "payload": payload, "seq": self._next_seq(user_id)}
        )
        for ws in connections:
            await ws.send_text(message)

    async def send_to_users(
        self, user_ids: Iterable[int], event_type: str, payload: object
    ) -> None:
        for user_id in user_ids:
            await self.send_to_user(user_id, event_type, payload)


manager = ConnectionManager()
