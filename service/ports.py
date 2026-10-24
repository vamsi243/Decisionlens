"""Ports: the three seams between the stream pipeline and its infrastructure.

Local adapters (file replay, in-memory store, WebSocket fan-out) implement them for
`RUN_MODE=local`; Azure adapters (Event Hubs, Cosmos DB, SignalR) implement the same
protocols for `RUN_MODE=azure` in Phase 8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from contracts import Event, KeyMoment, MatchMeta, MatchStats, Overlay, PlayerProfile
from contracts.stream import MomentAnalysis, ReplayStatus, Speed, StreamMessageType


@dataclass
class FramePacket:
    """One tracking frame plus the events stamped with it."""

    frame: int
    raw: bytes  # the TrackingFrame JSON exactly as received (forwarded without re-encoding)
    data: dict[str, Any]  # parsed frame
    events: list[Event] = field(default_factory=list)
    after_seek: bool = False  # the first packet after a seek: rebuild state before using it


class StreamSource(Protocol):
    """Where frames and events come from. The source owns pacing: `next_packet` waits on the
    replay clock (or on the network, for a live feed)."""

    meta: MatchMeta
    players: list[PlayerProfile]
    n_frames: int

    async def next_packet(self) -> FramePacket | None:
        """Next frame to process; None at full time. Blocks while paused."""
        ...

    def packet(self, frame: int) -> FramePacket:
        """Random access, used to rebuild state after a seek (replay sources only)."""
        ...

    def status(self) -> ReplayStatus: ...
    def play(self) -> None: ...
    def pause(self) -> None: ...
    def seek(self, t_ms: int) -> None: ...
    def set_speed(self, speed: Speed) -> None: ...


class StateStore(Protocol):
    """Shared state the API, the agents and the publisher read from."""

    def put_moment(self, m: KeyMoment) -> None: ...
    def moments(self, until_ms: int | None = None) -> list[KeyMoment]: ...
    def put_analysis(self, a: MomentAnalysis) -> None: ...
    def analysis(self, moment_id: str) -> MomentAnalysis | None: ...
    def put_overlay(self, o: Overlay) -> None: ...
    def overlay(self, overlay_id: str) -> Overlay | None: ...
    def overlays(self, until_ms: int | None = None) -> list[Overlay]: ...
    def put_stats(self, s: MatchStats) -> None: ...
    def stats(self) -> MatchStats | None: ...
    def reset_live(self) -> None: ...


class Publisher(Protocol):
    """Fan-out to connected boards."""

    async def publish(self, kind: StreamMessageType, data: Any) -> None: ...
    async def publish_raw(self, kind: StreamMessageType, raw: bytes) -> None: ...
