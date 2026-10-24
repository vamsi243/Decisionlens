"""Shared primitives: coordinates, probabilities, ranges.

Coordinate system: 105 x 68 m pitch, origin at the home team's defending bottom-left
corner, x along the length, y across the width, z = ball height in metres.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
# Ball and players can briefly leave the field of play (throw-ins, run-offs, goal nets).
PITCH_MARGIN = 5.0

X = Annotated[float, Field(ge=-PITCH_MARGIN, le=PITCH_LENGTH + PITCH_MARGIN)]
Y = Annotated[float, Field(ge=-PITCH_MARGIN, le=PITCH_WIDTH + PITCH_MARGIN)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]
Score100 = Annotated[float, Field(ge=0.0, le=100.0)]
TimeMs = Annotated[int, Field(ge=0)]


class Contract(BaseModel):
    """Base for every record: strict about unknown fields."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Point(Contract):
    x: X
    y: Y


class ProbRange(Contract):
    """Monte Carlo spread: median with 10th-90th percentile."""

    median: Probability
    low: Probability
    high: Probability

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not (self.low <= self.median <= self.high):
            raise ValueError("ProbRange must satisfy low <= median <= high")
        return self


class Period(StrEnum):
    FIRST_HALF = "1H"
    SECOND_HALF = "2H"


class Persona(StrEnum):
    ANALYST = "analyst"
    FAN = "fan"
