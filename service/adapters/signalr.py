"""Azure SignalR Service (Free, serverless mode) via its data-plane REST API, version 2024-12-01.

Hybrid fan-out: SignalR Free allows 20,000 messages a day, far too few for 10 Hz frames, so it
carries only the low-rate messages (moments, analyses, cards, status, intensity). Frames, events,
stats and workload stay on the service's own WebSocket.

Auth is a Microsoft Entra token for `https://signalr.azure.com/.default` from the app's managed
identity (role: SignalR REST API Owner). No access key anywhere.

  broadcast:     POST {endpoint}/api/hubs/{hub}/:send?api-version=2024-12-01
                 body {"target": "message", "arguments": [<envelope json>]}
  client token:  POST {endpoint}/api/hubs/{hub}/:generateToken?minutesToExpire=60&api-version=...
                 -> {"token": "..."}; clients connect to {endpoint}/client/?hub={hub}
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

import httpx

from contracts.stream import StreamMessageType
from service.adapters.ws_publisher import WebSocketPublisher, encode

log = logging.getLogger("decision_lens.signalr")

API_VERSION = "2024-12-01"
SCOPE = "https://signalr.azure.com/.default"
TARGET = "message"
LOW_RATE = {
    StreamMessageType.MOMENT,
    StreamMessageType.ANALYSIS,
    StreamMessageType.OVERLAY,
    StreamMessageType.STATUS,
    StreamMessageType.INTENSITY,
}


class SignalRPublisher:
    def __init__(
        self,
        endpoint: str,
        hub: str,
        credential: Any,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.hub = hub
        self.credential = credential  # azure.identity.aio credential (async get_token)
        self.transport = transport
        self._token: tuple[str, float] | None = None
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1000)
        self._task: asyncio.Task[None] | None = None
        self.sent = 0

    async def _bearer(self) -> str:
        if self._token is None or self._token[1] - time.time() < 120:
            tok = await self.credential.get_token(SCOPE)
            self._token = (tok.token, float(tok.expires_on))
        return self._token[0]

    async def _post(self, path: str, params: dict[str, Any], json: Any | None) -> httpx.Response:
        async with httpx.AsyncClient(timeout=10, transport=self.transport) as client:
            res = await client.post(
                f"{self.endpoint}/api/hubs/{self.hub}/{path}",
                params={**params, "api-version": API_VERSION},
                headers={"Authorization": f"Bearer {await self._bearer()}"},
                json=json,
            )
        res.raise_for_status()
        return res

    async def send(self, envelope: bytes) -> None:
        await self._post(":send", {}, {"target": TARGET, "arguments": [envelope.decode()]})
        self.sent += 1

    async def negotiate(self, minutes: int = 60) -> dict[str, str]:
        res = await self._post(":generateToken", {"minutesToExpire": minutes}, None)
        return {
            "url": f"{self.endpoint}/client/?hub={self.hub}",
            "accessToken": res.json()["token"],
        }

    # ------------------------------------------------------------------ background sender
    async def start(self) -> None:
        self._task = asyncio.create_task(self._sender())

    async def _sender(self) -> None:
        while True:
            msg = await self._queue.get()
            try:
                await self.send(msg)
            except Exception as exc:
                log.warning("signalr broadcast failed: %s", exc)

    async def aclose(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def publish(self, kind: StreamMessageType, data: Any) -> None:
        if self._queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
        self._queue.put_nowait(encode(kind, data))

    async def publish_raw(self, kind: StreamMessageType, raw: bytes) -> None:
        return None  # frames never go over SignalR


class HybridPublisher:
    """Low-rate messages over SignalR, everything high-rate over the service WebSocket."""

    def __init__(self, ws: WebSocketPublisher, signalr: SignalRPublisher) -> None:
        self.ws = ws
        self.signalr = signalr

    async def publish(self, kind: StreamMessageType, data: Any) -> None:
        if kind in LOW_RATE:
            await self.signalr.publish(kind, data)
        else:
            await self.ws.publish(kind, data)

    async def publish_raw(self, kind: StreamMessageType, raw: bytes) -> None:
        await self.ws.publish_raw(kind, raw)
