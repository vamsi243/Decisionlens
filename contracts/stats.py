"""Interpret-stage records: live team stats, intensity windows and calibration."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from contracts.base import Contract, Probability, Score100, TimeMs


class TeamStats(Contract):
    team_id: str
    possession: Probability
    passes: Annotated[int, Field(ge=0)]
    passes_completed: Annotated[int, Field(ge=0)]
    pass_accuracy: Probability
    avg_pass_distance_m: Annotated[float, Field(ge=0)]
    avg_pass_speed_ms: Annotated[float, Field(ge=0)]
    shots: Annotated[int, Field(ge=0)]
    shots_on_target: Annotated[int, Field(ge=0)]
    goals: Annotated[int, Field(ge=0)]
    xg: Annotated[float, Field(ge=0)]
    max_shot_speed_ms: Annotated[float, Field(ge=0)]
    tackles_won: Annotated[int, Field(ge=0)]
    interceptions: Annotated[int, Field(ge=0)]
    distance_km: Annotated[float, Field(ge=0)]


class MatchStats(Contract):
    t_ms: TimeMs
    teams: Annotated[list[TeamStats], Field(min_length=2, max_length=2)]


class IntensityPoint(Contract):
    """Match intensity for one 5-minute window (0-100, computable live; see engine.metrics)."""

    window_start_ms: TimeMs
    window_end_ms: TimeMs
    index: Score100
    hsr_m: Annotated[float, Field(ge=0)]
    duels: Annotated[int, Field(ge=0)]
    shots: Annotated[int, Field(ge=0)]
    pressures: Annotated[int, Field(ge=0)]
    xg: Annotated[float, Field(ge=0)]
    goals: Annotated[int, Field(ge=0)]
    dangerous_turnovers: Annotated[int, Field(ge=0)]


class CalibrationBin(Contract):
    lo: Probability
    hi: Probability
    count: Annotated[int, Field(ge=0)]
    predicted: Probability
    observed: Probability


class CalibrationReport(Contract):
    model: str
    samples: Annotated[int, Field(ge=0)]
    brier: Annotated[float, Field(ge=0)]
    ece: Annotated[float, Field(ge=0)]
    bins: list[CalibrationBin]
