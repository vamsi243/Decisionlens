"""Explain-stage records: KeyMoment, OptionSet, WhatIf, Overlay."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import Field, model_validator

from contracts.base import Contract, Persona, Point, Probability, ProbRange, TimeMs
from contracts.match import Archetype


class MomentType(StrEnum):
    AERIAL_DUEL = "aerial_duel"
    RECOVERY_RUN = "recovery_run"
    BIG_CHANCE = "big_chance"
    LINE_BREAKING_PASS = "line_breaking_pass"
    PRESS_TURNOVER = "press_turnover"
    GOAL = "goal"
    FATIGUE_ALERT = "fatigue_alert"


class FrameRange(Contract):
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end < self.start:
            raise ValueError("frame_range end must be >= start")
        return self


class KeyMoment(Contract):
    moment_id: str
    t_ms: TimeMs
    type: MomentType
    team_id: str | None = None
    players: Annotated[list[str], Field(min_length=1)]
    frame_range: FrameRange
    event_id: str | None = None
    importance: Probability = 0.5
    title: str = ""


class ActionKind(StrEnum):
    PASS = "pass"
    CROSS = "cross"
    SHOT = "shot"
    DRIBBLE = "dribble"
    CARRY = "carry"
    CLEAR = "clear"
    HEADER = "header"
    RECOVERY_RUN = "recovery_run"


class Option(Contract):
    option_id: str
    action: ActionKind
    target_id: str | None = None
    target: Point
    p_success: Probability
    range: ProbRange
    xt_gain: Annotated[float, Field(ge=-1, le=1)]
    path: Annotated[list[Point], Field(min_length=2)]
    chosen: bool = False


class OptionSet(Contract):
    moment_id: str
    t_ms: TimeMs
    actor_id: str
    options: Annotated[list[Option], Field(min_length=1, max_length=4)]
    best_option_id: str

    @model_validator(mode="after")
    def _best_exists(self) -> Self:
        if self.best_option_id not in {o.option_id for o in self.options}:
            raise ValueError("best_option_id must refer to one of the options")
        return self


class ProfileKind(StrEnum):
    ACTUAL = "actual"
    ARCHETYPE = "archetype"
    CUSTOM = "custom"
    SUBSTITUTE = "substitute"


class ProfileRef(Contract):
    kind: ProfileKind
    player_id: str | None = None
    archetype: Archetype | None = None
    label: str


class Scenario(Contract):
    profile: ProfileRef
    p_success: Probability
    range: ProbRange


class Driver(Contract):
    """One reason the counterfactual differs, e.g. factor=jump_reach, delta=+12, unit=cm."""

    factor: str
    delta: float
    unit: str
    text: str


class WhatIf(Contract):
    moment_id: str
    actor_id: str
    actual: Scenario
    counterfactual: Scenario
    drivers: list[Driver]
    ghost_path: list[Point] = []


class OverlayKind(StrEnum):
    MOMENT = "moment"
    OPTIONS = "options"
    WHAT_IF = "what_if"
    STAT = "stat"
    FATIGUE = "fatigue"
    RECAP = "recap"


class Overlay(Contract):
    overlay_id: str
    t_ms: TimeMs
    show_for_ms: Annotated[int, Field(gt=0)] = 8000
    kind: OverlayKind
    moment_id: str | None = None
    payload: dict[str, Any] = {}
    # text[persona][language code] -> card text, e.g. text["fan"]["en"]
    text: dict[Persona, dict[str, str]] = {}
    grounded: bool = False
    source: str = "engine"
