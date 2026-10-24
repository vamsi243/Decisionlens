"""A player's decisions, ranked by what they cost (or earned) in goal odds.

On the ball: at every pass, shot, cross or dribble the option scorer's candidates are weighed by
their *goal odds*, the chance the possession ends in a goal: xG for a shot, p_success x threat at
the end point for a pass, cross or carry (the threat grid is exactly that chance). The gap between
the best candidate and the one chosen is what the decision cost.

Defending: a lost tackle or aerial duel, or being dribbled past, that the opponents turned into a
shot within 15 s. It costs that shot's xG. The last defender involved is the one blamed, which is
a rule of thumb rather than ground truth.

Both are in the same unit (chance of a goal), so they rank together.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np

from contracts import ActionKind, Event, EventType, Outcome
from contracts.player import (
    Consequence,
    DecisionKind,
    DecisionOption,
    PlayerDecision,
)
from engine.metrics import shot_xg
from engine.options import _Cand, _matches, candidates
from engine.snapshot import Snapshot
from engine.xt import xt

WINDOW_MS = 15_000  # what followed: the next 15 seconds
MIN_GAIN = 0.01  # under one point of goal odds the choice was as good as the best
ON_BALL = {EventType.PASS, EventType.SHOT, EventType.CROSS, EventType.DRIBBLE}
TOP_NEGATIVE = 3
MIN_POSITIVE = 0.03  # a 'best decision' worth showing gave at least 3% goal odds
BAD = {Consequence.LOST_BALL, Consequence.SHOT_AGAINST, Consequence.GOAL_AGAINST}


def goal_odds(c: _Cand, here: float) -> float:
    if c.action == ActionKind.SHOT:
        return float(c.p)
    return float(c.p * np.clip(here + c.xt_gain, 0.0, 1.0))


def _option(c: _Cand, here: float) -> DecisionOption:
    return DecisionOption(
        action=c.action,
        target_id=c.target_id,
        p_success=round(float(c.p), 4),
        goal_odds=round(goal_odds(c, here), 4),
    )


def consequence(
    after: Iterable[Event], team: str | None, home: str, finishing: Mapping[str, float]
) -> tuple[Consequence, float | None]:
    """The first goal or shot by either side in the window after a decision."""
    for f in after:
        if f.type == EventType.GOAL:
            return (Consequence.GOAL_FOR if f.team_id == team else Consequence.GOAL_AGAINST), None
        if f.type == EventType.SHOT:
            x = round(shot_xg(f, home, finishing.get(f.player_id or "", 70.0)), 4)
            if f.outcome == Outcome.SUCCESS:
                return (Consequence.GOAL_FOR if f.team_id == team else Consequence.GOAL_AGAINST), x
            return (Consequence.SHOT_FOR if f.team_id == team else Consequence.SHOT_AGAINST), x
    return Consequence.NONE, None


def window(events: list[Event], i: int) -> list[Event]:
    """Events in the 15 s after events[i] (events sorted by time)."""
    t = events[i].t_ms
    out = []
    for f in events[i + 1 :]:
        if f.t_ms > t + WINDOW_MS:
            break
        out.append(f)
    return out


def score_on_ball(
    snap: Snapshot,
    e: Event,
    after: list[Event],
    finishing: Mapping[str, float],
) -> PlayerDecision | None:
    """Chosen vs best (by goal odds) for one on-ball event, or None if it can't be matched."""
    actor = e.player_id
    if actor is None or actor not in snap.ids:
        return None
    pinned = {}
    if e.type == EventType.PASS and e.target_id and e.end:
        pinned[e.target_id] = np.array([e.end.x, e.end.y])
    cands = candidates(snap, actor, pinned)
    chosen = next((c for c in cands if _matches(c, e)), None)
    if chosen is None:  # e.g. a pass to the goalkeeper, which isn't a candidate
        return None
    team = snap.team_of(actor)
    fx, fy = (float(v) for v in snap.rel(team, snap.pos[snap.idx(actor)]))
    here = xt(fx, fy)
    best = max(cands, key=lambda c: goal_odds(c, here))
    gain = goal_odds(best, here) - goal_odds(chosen, here)
    if gain < MIN_GAIN:
        best, gain = chosen, 0.0
    x: float | None
    if e.type == EventType.SHOT:  # the shot itself is what followed
        x = round(goal_odds(chosen, here), 4)
        cons = Consequence.GOAL_FOR if e.outcome == Outcome.SUCCESS else Consequence.SHOT_FOR
    else:
        cons, x = consequence(after, e.team_id, snap.home_team, finishing)
        if cons == Consequence.NONE and e.outcome == Outcome.FAIL:
            cons = Consequence.LOST_BALL
    return PlayerDecision(
        decision_id=f"dec_{e.event_id}",
        player_id=actor,
        t_ms=e.t_ms,
        frame=e.frame_ref,
        kind=DecisionKind.ON_BALL,
        chosen=_option(chosen, here),
        best=_option(best, here),
        goal_odds_gain=round(gain, 4),
        consequence=cons,
        consequence_xg=x,
    )


def defending(
    events: list[Event],
    player_id: str,
    team_of: Mapping[str, str],
    home: str,
    finishing: Mapping[str, float],
) -> list[PlayerDecision]:
    """Duels and tackles `player_id` lost that the opponents turned into a shot or goal."""
    out = []
    for i, e in enumerate(events):
        lost = (
            (e.type in (EventType.TACKLE, EventType.AERIAL_DUEL) and e.outcome == Outcome.FAIL)
            and e.player_id == player_id
        ) or (
            e.type == EventType.DRIBBLE
            and e.outcome == Outcome.SUCCESS
            and e.target_id == player_id
        )
        if not lost:
            continue
        cons, x = consequence(window(events, i), team_of.get(player_id), home, finishing)
        if cons not in (Consequence.SHOT_AGAINST, Consequence.GOAL_AGAINST):
            continue
        out.append(
            PlayerDecision(
                decision_id=f"dec_{e.event_id}",
                player_id=player_id,
                t_ms=e.t_ms,
                frame=e.frame_ref,
                kind=DecisionKind.DEFENDING,
                consequence=cons,
                consequence_xg=x,
            )
        )
    return out


def impact(d: PlayerDecision) -> float:
    """How much a decision cost in goal odds: the missed gain, or the xG it handed over."""
    if d.kind == DecisionKind.DEFENDING:
        return (d.consequence_xg or 0.0) + (0.3 if d.consequence == Consequence.GOAL_AGAINST else 0)
    bonus = 0.05 if d.consequence in (Consequence.GOAL_AGAINST, Consequence.SHOT_AGAINST) else 0
    return d.goal_odds_gain + bonus


def top_decisions(scored: list[PlayerDecision], limit: int = TOP_NEGATIVE) -> list[PlayerDecision]:
    """The costliest few plus the best one they got right, so the panel isn't all negative."""
    costly = sorted(
        (
            d
            for d in scored
            if impact(d) >= MIN_GAIN
            and not (d.kind == DecisionKind.ON_BALL and d.goal_odds_gain == 0)
        ),
        key=impact,
        reverse=True,
    )[:limit]
    good = [
        d
        for d in scored
        if d.kind == DecisionKind.ON_BALL
        and d.goal_odds_gain == 0
        and d.chosen is not None
        and d.chosen.goal_odds >= MIN_POSITIVE
        and d.consequence not in BAD
    ]
    best_good = max(
        good,
        key=lambda d: (
            d.consequence == Consequence.GOAL_FOR,
            d.chosen.goal_odds if d.chosen else 0.0,
        ),
        default=None,
    )
    picked = [d.model_copy(update={"positive": False}) for d in costly]
    if best_good is not None:
        picked.append(best_good.model_copy(update={"positive": True}))
    return sorted(picked, key=lambda d: d.t_ms)
