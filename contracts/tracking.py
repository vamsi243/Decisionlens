"""High-frequency records: TrackingFrame (10 Hz), Event (per action), WorkloadState (1 Hz)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field

from contracts.base import Contract, Period, Point, Probability, Score100, TimeMs, X, Y


class BallState(Contract):
    x: X
    y: Y
    z: Annotated[float, Field(ge=0, le=40)]
    owner_id: str | None = None


class PlayerTrack(Contract):
    id: str
    x: X
    y: Y
    vx: float
    vy: float


class TrackingFrame(Contract):
    frame: Annotated[int, Field(ge=0)]
    t_ms: TimeMs
    period: Period
    ball: BallState
    players: list[PlayerTrack]


class EventType(StrEnum):
    PASS = "pass"
    CROSS = "cross"
    SHOT = "shot"
    DRIBBLE = "dribble"
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    AERIAL_DUEL = "aerial_duel"
    CLEARANCE = "clearance"
    FOUL = "foul"
    POSSESSION_CHANGE = "possession_change"
    PRESSURE = "pressure"
    SUBSTITUTION = "substitution"
    GOAL = "goal"
    KNOCK = "knock"
    PERIOD_START = "period_start"
    PERIOD_END = "period_end"


class Outcome(StrEnum):
    SUCCESS = "success"
    FAIL = "fail"


class Event(Contract):
    event_id: str
    t_ms: TimeMs
    period: Period
    type: EventType
    team_id: str | None = None
    player_id: str | None = None
    start: Point | None = None
    end: Point | None = None
    target_id: str | None = None
    outcome: Outcome | None = None
    ball_speed_ms: Annotated[float, Field(ge=0, le=50)] | None = None
    ball_height_m: Annotated[float, Field(ge=0, le=40)] | None = None
    pressure: Probability | None = None
    tags: list[str] = []
    frame_ref: Annotated[int, Field(ge=0)]


class PhysicalStatus(StrEnum):
    FIT = "fit"
    TIRING = "tiring"
    FATIGUED = "fatigued"
    KNOCK = "knock"


class Modifiers(Contract):
    """Multipliers applied to a player's physical profile (1.0 = fresh)."""

    speed: Annotated[float, Field(ge=0.5, le=1.0)] = 1.0
    accel: Annotated[float, Field(ge=0.5, le=1.0)] = 1.0
    reaction: Annotated[float, Field(ge=1.0, le=1.6)] = 1.0


class WorkloadState(Contract):
    t_ms: TimeMs
    player_id: str
    distance_m: Annotated[float, Field(ge=0)]
    hsr_m: Annotated[float, Field(ge=0)]
    sprints: Annotated[int, Field(ge=0)]
    recent_load: Annotated[float, Field(ge=0)]
    fatigue: Score100
    status: PhysicalStatus
    modifiers: Modifiers = Modifiers()
