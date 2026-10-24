"""Static match records: MatchMeta (once) and PlayerProfile (once per player)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, model_validator

from contracts.base import PITCH_LENGTH, PITCH_WIDTH, Contract, Score100

HexColour = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


class TeamColours(Contract):
    primary: HexColour
    secondary: HexColour


class TeamMeta(Contract):
    team_id: str
    name: str
    short_name: Annotated[str, Field(max_length=4)]
    formation: Annotated[str, Field(pattern=r"^\d(-\d){2,4}$")]
    colours: TeamColours
    is_home: bool


class PitchSize(Contract):
    length: float = PITCH_LENGTH
    width: float = PITCH_WIDTH


class MatchMeta(Contract):
    match_id: str
    seed: int
    teams: Annotated[list[TeamMeta], Field(min_length=2, max_length=2)]
    pitch: PitchSize = PitchSize()
    tracking_hz: Annotated[int, Field(ge=1, le=50)] = 10
    period_length_ms: Annotated[int, Field(gt=0)] = 45 * 60 * 1000
    venue: str = "Synthetic Stadium"
    synthetic: bool = True

    @model_validator(mode="after")
    def _one_home_team(self) -> Self:
        if sum(t.is_home for t in self.teams) != 1:
            raise ValueError("exactly one team must be home")
        if self.teams[0].team_id == self.teams[1].team_id:
            raise ValueError("team ids must differ")
        return self


class Position(StrEnum):
    GK = "GK"
    CB = "CB"
    FB = "FB"
    DM = "DM"
    CM = "CM"
    AM = "AM"
    W = "W"
    ST = "ST"


class Archetype(StrEnum):
    GOALKEEPER = "goalkeeper"
    AERIAL_CB = "aerial_cb"
    BALL_PLAYING_CB = "ball_playing_cb"
    OVERLAPPING_FB = "overlapping_fb"
    DEEP_PLAYMAKER = "deep_playmaker"
    BOX_TO_BOX = "box_to_box"
    PRESSING_FORWARD = "pressing_forward"
    TARGET_MAN = "target_man"
    WINGER = "winger"


class Physical(Contract):
    height_cm: Annotated[float, Field(ge=150, le=210)]
    max_speed_ms: Annotated[float, Field(ge=5, le=11)]
    accel_ms2: Annotated[float, Field(ge=1, le=8)]
    reaction_s: Annotated[float, Field(ge=0.1, le=0.6)]
    jump_reach_cm: Annotated[float, Field(ge=180, le=320)]


class Skill(Contract):
    passing: Score100
    aerial: Score100
    tackle: Score100
    finishing: Score100


class PlayerProfile(Contract):
    player_id: str
    team_id: str
    name: str
    shirt_number: Annotated[int, Field(ge=1, le=99)]
    position: Position
    archetype: Archetype
    starter: bool
    physical: Physical
    skill: Skill
