"""CosmosStore: StateStore for RUN_MODE=azure (Cosmos DB for NoSQL, free tier).

Reads stay in memory, so they're synchronous and fast. Every write is mirrored to Cosmos in the
background. At start-up the store reloads moments, analyses, cards and the agent response
cache, so a container that scaled to zero wakes up with every card it already paid for.

One container, partition key `/match_id`; documents are `{id, match_id, kind, data}`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from contracts import KeyMoment, MatchStats, Overlay
from contracts.stream import MomentAnalysis
from service.adapters.memory_store import MemoryStore

log = logging.getLogger("decision_lens.cosmos")

KINDS = ("moment", "analysis", "overlay", "cache")


def _doc_id(kind: str, key: str) -> str:
    # Cosmos ids may not contain '/', '\\', '?' or '#'
    safe = key.replace("/", "_").replace("\\", "_").replace("?", "_").replace("#", "_")
    return f"{kind}:{safe}"[:255]


class CosmosStore(MemoryStore):
    def __init__(self, container: Any, match_id: str) -> None:
        super().__init__()
        self.container = container  # azure.cosmos.aio ContainerProxy (or a test double)
        self.match_id = match_id
        self.cache: dict[str, str] = {}  # agent response cache, mirrored to Cosmos
        self._writes: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        await self.hydrate()
        self._task = asyncio.create_task(self._writer())

    async def hydrate(self) -> None:
        n = 0
        query = "SELECT * FROM c WHERE c.match_id = @m"
        items = self.container.query_items(
            query=query,
            parameters=[{"name": "@m", "value": self.match_id}],
            partition_key=self.match_id,
        )
        async for doc in items:
            kind, data = doc.get("kind"), doc.get("data")
            if kind == "moment":
                super().put_moment(KeyMoment.model_validate(data))
            elif kind == "analysis":
                super().put_analysis(MomentAnalysis.model_validate(data))
            elif kind == "overlay":
                super().put_overlay(Overlay.model_validate(data))
            elif kind == "cache":
                self.cache[doc["key"]] = data
            n += 1
        log.info("hydrated %d documents for %s", n, self.match_id)

    async def _writer(self) -> None:
        while True:
            doc = await self._writes.get()
            try:
                await self.container.upsert_item(doc)
            except Exception:
                log.exception("cosmos upsert failed for %s", doc.get("id"))
            finally:
                self._writes.task_done()

    async def flush(self) -> None:
        await self._writes.join()

    async def aclose(self) -> None:
        if self._task:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.flush(), 5)
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    def _enqueue(self, kind: str, key: str, data: Any) -> None:
        doc = {"id": _doc_id(kind, key), "match_id": self.match_id, "kind": kind, "data": data}
        if kind == "cache":
            doc["key"] = key
        self._writes.put_nowait(doc)

    # ------------------------------------------------------------------ StateStore
    def put_moment(self, m: KeyMoment) -> None:
        new = m.moment_id not in self._moments  # replays re-detect moments: write once
        super().put_moment(m)
        if new:
            self._enqueue("moment", m.moment_id, m.model_dump(mode="json"))

    def put_analysis(self, a: MomentAnalysis) -> None:
        super().put_analysis(a)
        self._enqueue("analysis", a.moment.moment_id, a.model_dump(mode="json"))

    def put_overlay(self, o: Overlay) -> None:
        super().put_overlay(o)
        self._enqueue("overlay", o.overlay_id, o.model_dump(mode="json"))

    def put_stats(self, s: MatchStats) -> None:
        super().put_stats(s)  # live stats are recomputed on wake; not worth the RUs

    # ------------------------------------------------------------------ agent cache sink
    def put_cache(self, key: str, text: str) -> None:
        self.cache[key] = text
        self._enqueue("cache", key, text)


async def open_container(endpoint: str, database: str, container: str, credential: Any) -> Any:
    """Container client using the managed identity (Cosmos data-plane RBAC, no keys)."""
    from azure.cosmos.aio import CosmosClient

    client = CosmosClient(endpoint, credential=credential)
    return client.get_database_client(database).get_container_client(container)
