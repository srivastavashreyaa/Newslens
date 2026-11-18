import asyncio
import json
import logging

from fastapi import WebSocket

log = logging.getLogger("ws")


class ConnectionManager:
    """Broadcasts newly analyzed articles to every connected dashboard."""

    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._clients.discard(ws)

    @property
    def count(self) -> int:
        return len(self._clients)

    async def broadcast(self, message: dict):
        if not self._clients:
            return
        data = json.dumps(message)
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_text(data)
            except Exception:
                await self.disconnect(ws)


manager = ConnectionManager()
