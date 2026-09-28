import asyncio
from collections.abc import Iterable
from contextlib import suppress
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder


class RealtimeManager:
    def __init__(self) -> None:
        self.websockets: set[WebSocket] = set()
        self.subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.websockets.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.websockets.discard(websocket)

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self.subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self.subscribers.discard(queue)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        payload = jsonable_encoder(payload)
        async with self._lock:
            websocket_targets = list(self.websockets)
            queue_targets = list(self.subscribers)
        dead: list[WebSocket] = []
        for websocket in websocket_targets:
            try:
                await websocket.send_json(payload)
            except (RuntimeError, WebSocketDisconnect, OSError):
                dead.append(websocket)
        for websocket in dead:
            await self.disconnect(websocket)
        for queue in queue_targets:
            if queue.full():
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(payload)

    async def broadcast_many(self, payloads: Iterable[dict[str, Any]]) -> None:
        for payload in payloads:
            await self.broadcast(payload)


realtime = RealtimeManager()
