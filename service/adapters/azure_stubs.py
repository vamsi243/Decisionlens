"""Azure adapters (Phase 8): Event Hubs source, Cosmos DB store, SignalR publisher.

They implement the same ports as the local adapters. Until Phase 8 they only say so.
"""

from __future__ import annotations

PHASE_8 = "Azure adapters arrive in Phase 8; run with RUN_MODE=local for now."


class EventHubsSource:
    def __init__(self, *_: object, **__: object) -> None:
        raise NotImplementedError(PHASE_8)


class CosmosStore:
    def __init__(self, *_: object, **__: object) -> None:
        raise NotImplementedError(PHASE_8)


class SignalRPublisher:
    def __init__(self, *_: object, **__: object) -> None:
        raise NotImplementedError(PHASE_8)
