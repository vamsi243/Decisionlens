"""WebSocketPublisher: fans messages out to every connected board.

Each client gets its own bounded queue and sender task, so one slow browser never stalls the
pipeline. If a client falls behind, the oldest messages are dropped (a fresh frame is worth
more than a stale one); moments and analyses are rare and small enough that this is harmless.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import orjson
from fastapi import WebSocket
from pydantic import BaseModel

from contracts.stream import StreamMessageType

QUEUE_SIZE = 512


def encode(kind: StreamMessageType, data: Any) -> bytes:
    payload: Any
    if isinstance(data, BaseModel):
        payload = data.model_dump(mode="json", exclude_none=True)
    elif isinstance(data, list):
        payload = [
            d.model_dump(mode="json", exclude_none=True) if isinstance(d, BaseModel) else d
            for d in data
        ]
    else:
        payload = data
    return orjson.dumps({"type": kind.value, "data": payload})


def envelope(kind: StreamMessageType, raw: bytes) -> bytes:
    return b'{"type":"' + kind.value.encode() + b'","data":' + raw + b"}"


class _Client:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.queue: asyncio.Queue[bytes] = asyncio.Queue(QUEUE_SIZE)
        self.task: asyncio.Task[None] | None = None

    def offer(self, msg: bytes) -> None:
        if self.queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
        self.queue.put_nowait(msg)

    async def run(self) -> None:
        while True:
            msg = await self.queue.get()
            await self.ws.send_text(msg.decode())


class WebSocketPublisher:
    def __init__(self) -> None:
        self.clients: set[_Client] = set()

    @property
    def count(self) -> int:
        return len(self.clients)

    async def publish(self, kind: StreamMessageType, data: Any) -> None:
        if self.clients:
            self._fan_out(encode(kind, data))

    async def publish_raw(self, kind: StreamMessageType, raw: bytes) -> None:
        if self.clients:
            self._fan_out(envelope(kind, raw))

    def _fan_out(self, msg: bytes) -> None:
        for c in list(self.clients):
            c.offer(msg)

    async def serve(self, ws: WebSocket, hello: bytes) -> None:
        """Run one client until it disconnects. `hello` is sent first."""
        client = _Client(ws)
        client.offer(hello)
        self.clients.add(client)
        client.task = asyncio.create_task(client.run())
        try:
            while True:  # we only listen to notice disconnects; control is REST
                await ws.receive_text()
        except Exception:
            pass
        finally:
            self.clients.discard(client)
            client.task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await client.task
