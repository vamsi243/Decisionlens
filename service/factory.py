"""One place that picks adapters for RUN_MODE=local | azure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from service.adapters.azure_stubs import CosmosStore, EventHubsSource, SignalRPublisher
from service.adapters.file_replay import FileReplay
from service.adapters.memory_store import MemoryStore
from service.adapters.ws_publisher import WebSocketPublisher
from service.ports import Publisher, StateStore, StreamSource
from service.settings import Settings


@dataclass
class Adapters:
    source: StreamSource
    store: StateStore
    publisher: Publisher
    ws: WebSocketPublisher | None  # the local fan-out, when boards connect to us directly


def build_adapters(settings: Settings) -> Adapters:
    if settings.run_mode == "azure":
        return Adapters(
            cast(StreamSource, EventHubsSource()),
            cast(StateStore, CosmosStore()),
            cast(Publisher, SignalRPublisher()),
            None,
        )
    ws = WebSocketPublisher()
    speed = int(settings.replay_speed)
    return Adapters(
        source=FileReplay(settings.match_dir, speed=speed if speed in (1, 2, 4, 8) else 1),  # type: ignore[arg-type]
        store=MemoryStore(),
        publisher=ws,
        ws=ws,
    )
