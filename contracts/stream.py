"""Stream records: replay status, moment analysis and the WebSocket envelope.

Every WebSocket message is `{"type": <StreamMessageType>, "data": ...}`:

| type      | data                                            | cadence                  |
| --------- | ----------------------------------------------- | ------------------------ |
| hello     | `Hello` (meta, players, status, moments, stats) | once on connect          |
| frame     | `TrackingFrame`                                 | every frame              |
| event     | `Event`                                         | per action               |
| stats     | `MatchStats`                                    | every match second       |
| workload  | list of `WorkloadState` (on the pitch)          | every 5 match seconds    |
| intensity | list of `IntensityPoint`                        | every match minute       |
| moment    | `KeyMoment`                                     | when detected            |
| analysis  | `MomentAnalysis` (option map + what-if)         | when computed            |
| overlay   | `Overlay`                                       | when a card is ready     |
| status    | `ReplayStatus`                                  | play, pause, seek, speed |
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from contracts.analysis import KeyMoment, OptionSet, WhatIf
from contracts.base import Contract, Period, TimeMs
from contracts.match import MatchMeta, PlayerProfile
from contracts.stats import MatchStats

Speed = Literal[1, 2, 4, 8]


class StreamMessageType(StrEnum):
    HELLO = "hello"
    FRAME = "frame"
    EVENT = "event"
    STATS = "stats"
    WORKLOAD = "workload"
    INTENSITY = "intensity"
    MOMENT = "moment"
    ANALYSIS = "analysis"
    OVERLAY = "overlay"
    STATUS = "status"


class ReplayStatus(Contract):
    playing: bool
    speed: Speed
    frame: Annotated[int, Field(ge=0)]
    t_ms: TimeMs
    period: Period
    duration_ms: TimeMs
    live: bool = False  # True for a true live feed (no seeking)


class MomentAnalysis(Contract):
    moment: KeyMoment
    options: OptionSet | None = None
    what_if: WhatIf | None = None


class Hello(Contract):
    meta: MatchMeta
    players: list[PlayerProfile]
    status: ReplayStatus
    moments: list[KeyMoment]
    stats: MatchStats | None = None
