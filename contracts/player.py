"""Per-player records: live stats for the hover card and the decisions behind the player panel."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field

from contracts.analysis import ActionKind
from contracts.base import Contract, Persona, Probability, TimeMs
from contracts.match import Foot
from contracts.tracking import PhysicalStatus

Count = Annotated[int, Field(ge=0)]


class PlayerStats(Contract):
    """Everything known about one player up to `t_ms`: workload plus counts from the events."""

    player_id: str
    t_ms: TimeMs
    on_pitch: bool
    distance_km: Annotated[float, Field(ge=0)]
    hsr_m: Annotated[float, Field(ge=0)]
    sprints: Count
    fatigue: Annotated[float, Field(ge=0, le=100)]
    top_speed_loss_pct: Annotated[int, Field(ge=0, le=100)]
    status: PhysicalStatus
    passes: Count = 0
    passes_completed: Count = 0
    shots: Count = 0
    goals: Count = 0
    tackles: Count = 0
    tackles_won: Count = 0
    interceptions: Count = 0
    aerial_duels: Count = 0
    aerial_won: Count = 0
    dribbles: Count = 0
    dribbles_won: Count = 0
    fouls: Count = 0


class DecisionKind(StrEnum):
    ON_BALL = "on_ball"  # a pass, shot, cross or dribble, scored against the alternatives
    DEFENDING = "defending"  # a lost duel or tackle that the opponents turned into a shot


class Consequence(StrEnum):
    GOAL_FOR = "goal_for"
    SHOT_FOR = "shot_for"
    GOAL_AGAINST = "goal_against"
    SHOT_AGAINST = "shot_against"
    LOST_BALL = "lost_ball"
    NONE = "none"


class DecisionOption(Contract):
    action: ActionKind
    target_id: str | None = None
    p_success: Probability
    # Chance the possession ends in a goal: xG for a shot, p_success x threat at the end point
    # for a pass, cross or carry.
    goal_odds: Probability


class PlayerDecision(Contract):
    decision_id: str
    player_id: str
    t_ms: TimeMs
    frame: Annotated[int, Field(ge=0)]
    kind: DecisionKind
    chosen: DecisionOption | None = None
    best: DecisionOption | None = None
    goal_odds_gain: float = 0.0  # best minus chosen; 0 when the best option was taken
    consequence: Consequence = Consequence.NONE
    consequence_xg: Probability | None = None  # xG of the shot that followed, if any
    positive: bool = False
    # text[persona]["en"] -> one line for the panel; agents rewrite it at the whistles
    text: dict[Persona, dict[str, str]] = {}
    source: str = "engine"


class PlayerDecisions(Contract):
    player_id: str
    t_ms: TimeMs
    items: list[PlayerDecision]


class MarkerOption(Contract):
    """One candidate to mark an opponent, scored by the engine's own duel models."""

    player_id: str
    on_pitch: bool  # False: a fresh substitute on the bench
    score: Probability  # weighted duel score x position fit (+ foot bonus)
    aerial: Probability  # P(wins a header against the attacker)
    ground: Probability  # P(wins a ground duel / tackle)
    race: Probability  # P(catches the attacker in a foot race)
    position_fit: Probability
    foot: Foot
    foot_match: bool | None = None  # None when the attacker plays through the middle
    fatigue: Annotated[float, Field(ge=0, le=100)]
    reasons: list[str] = []  # engine wording, e.g. "+12 cm reach", "fresh legs"


class MarkingAdvice(Contract):
    attacker_id: str
    t_ms: TimeMs
    channel: str  # where the attacker plays, from the defending side: left | centre | right
    weights: dict[str, float]  # what this attacker asks of a marker: aerial / ground / race
    options: list[MarkerOption]
    excluded: list[str] = []
