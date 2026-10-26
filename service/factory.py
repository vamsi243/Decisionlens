"""One place that picks adapters for RUN_MODE=local | azure.

| Port          | local               | azure (each falls back to local if not configured)        |
| ------------- | ------------------- | --------------------------------------------------------- |
| StreamSource  | FileReplay          | EventHubsSource (+ in-process EventHubsBroadcaster)       |
| StateStore    | MemoryStore         | CosmosStore (write-through, hydrated on start)            |
| Publisher     | WebSocketPublisher  | HybridPublisher: SignalR (low-rate) + WebSocket (frames)  |

Azure clients authenticate with the app's managed identity (DefaultAzureCredential): no keys.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from service.adapters.file_replay import FileReplay
from service.adapters.memory_store import MemoryStore
from service.adapters.ws_publisher import WebSocketPublisher
from service.ports import Publisher, StateStore, StreamSource
from service.settings import Settings

log = logging.getLogger("decision_lens.factory")


@dataclass
class Adapters:
    source: StreamSource
    store: StateStore
    publisher: Publisher
    ws: WebSocketPublisher | None  # the local fan-out boards connect to for frames
    archive: FileReplay  # the match file: warm-up, recap, clips, state restoration
    signalr: Any = None  # SignalRPublisher when configured (for /negotiate)
    background: list[Callable[[], Coroutine[Any, Any, None]]] = field(default_factory=list)
    closers: list[Callable[[], Awaitable[None]]] = field(default_factory=list)
    cache_initial: dict[str, str] = field(default_factory=dict)
    cache_sink: Callable[[str, str], None] | None = None

    @property
    def live(self) -> bool:
        return bool(self.source.status().live)


def data_version(match_dir: str | Path) -> str:
    """Short hash of the match files and the engine code.

    Moment ids, numbers and cached agent text all follow from these, so the Cosmos partition is
    `<match_id>@<version>`: a regenerated match or a new engine never wakes up with the old cards.
    """
    h = hashlib.sha256()
    root = Path(__file__).resolve().parent.parent
    files = sorted(Path(match_dir).glob("*.jsonl*")) + sorted((root / "engine").glob("*.py"))
    for f in files:
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


def _speed(settings: Settings) -> Any:
    s = int(settings.replay_speed)
    return s if s in (1, 2, 4, 8) else 1


async def build_adapters(settings: Settings) -> Adapters:
    archive = FileReplay(settings.match_dir, speed=_speed(settings))
    ws = WebSocketPublisher()
    if settings.run_mode != "azure":
        if settings.live_simulation:  # the live-broadcast path, looped back in-process
            from service.adapters.event_hubs import (
                EventHubsBroadcaster,
                EventHubsSource,
                LoopbackProducer,
            )

            live = EventHubsSource(archive, consumer=None)
            caster = EventHubsBroadcaster(archive, LoopbackProducer(live))
            return Adapters(live, MemoryStore(), ws, ws, archive, background=[caster.run])
        return Adapters(archive, MemoryStore(), ws, ws, archive)

    from azure.identity.aio import DefaultAzureCredential

    cred = DefaultAzureCredential()
    adapters = Adapters(archive, MemoryStore(), ws, ws, archive)
    adapters.closers.append(cred.close)

    if settings.eventhub_namespace:
        from azure.eventhub.aio import EventHubConsumerClient, EventHubProducerClient

        from service.adapters.event_hubs import EventHubsBroadcaster, EventHubsSource

        consumer = EventHubConsumerClient(
            settings.eventhub_namespace,
            settings.eventhub_name,
            settings.eventhub_consumer_group,
            cred,
        )
        source = EventHubsSource(archive, consumer)
        await source.start()
        adapters.source = source
        adapters.closers.append(source.aclose)
        if settings.broadcast_producer:
            producer = EventHubProducerClient(
                settings.eventhub_namespace, settings.eventhub_name, cred
            )
            adapters.background.append(EventHubsBroadcaster(archive, producer).run)
            adapters.closers.append(producer.close)
        log.info("live broadcast from Event Hubs %s", settings.eventhub_name)

    if settings.cosmos_endpoint:
        from service.adapters.cosmos import CosmosStore, open_container

        container = await open_container(
            settings.cosmos_endpoint, settings.cosmos_database, settings.cosmos_container, cred
        )
        partition = f"{archive.meta.match_id}@{data_version(settings.match_dir)}"
        store = CosmosStore(container, partition)
        log.info("cosmos partition %s", partition)
        await store.start()
        adapters.store = store
        adapters.cache_initial = dict(store.cache)
        adapters.cache_sink = store.put_cache
        adapters.closers.append(store.aclose)

    if settings.signalr_endpoint:
        from service.adapters.signalr import HybridPublisher, SignalRPublisher

        sr = SignalRPublisher(settings.signalr_endpoint, settings.signalr_hub, cred)
        await sr.start()
        adapters.signalr = sr
        adapters.publisher = HybridPublisher(ws, sr)
        adapters.closers.append(sr.aclose)

    if not adapters.live:  # no Event Hubs configured: play the file on a loop instead
        archive.play()
    return adapters
