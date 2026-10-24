"""Who should mark whom: every candidate scored with the engine's own duel models.

For an attacker X and each possible marker D (on the pitch, or a fresh substitute):
- aerial: P(D wins a header against X) from `aerial_win`, both arriving at a dropping ball;
- race: P(D catches X in a foot race) from `recovery_run`, D starting a few metres behind;
- ground: P(D wins a tackle against X) from `duel_success`, tackling vs X's carrying skill.
Both players are slowed by their live fatigue. What X asks of a marker depends on X's type
(a target man is mostly headers, a winger mostly races and one-on-ones), so the three are
weighted by X's archetype. The result is scaled by how well D's positions fit the job and
gets a small bonus when D's stronger foot matches the side X attacks.

The scenarios are standardised (same distances for everyone), so the scores compare markers
with each other; they are not the odds of any one real duel.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np

from contracts import Archetype, Foot, Modifiers, PlayerProfile, Position
from contracts.player import MarkerOption, MarkingAdvice
from engine.physics import Kinematics
from engine.probability import aerial_win, duel_success, recovery_run
from engine.profiles import effective_reach_cm

WEIGHTS: dict[Archetype, dict[str, float]] = {
    Archetype.TARGET_MAN: {"aerial": 0.6, "ground": 0.25, "race": 0.15},
    Archetype.WINGER: {"aerial": 0.1, "ground": 0.4, "race": 0.5},
    Archetype.PRESSING_FORWARD: {"aerial": 0.2, "ground": 0.4, "race": 0.4},
    Archetype.OVERLAPPING_FB: {"aerial": 0.1, "ground": 0.4, "race": 0.5},
    Archetype.BOX_TO_BOX: {"aerial": 0.25, "ground": 0.45, "race": 0.3},
    Archetype.DEEP_PLAYMAKER: {"aerial": 0.15, "ground": 0.6, "race": 0.25},
    Archetype.AERIAL_CB: {"aerial": 0.7, "ground": 0.2, "race": 0.1},
    Archetype.BALL_PLAYING_CB: {"aerial": 0.4, "ground": 0.4, "race": 0.2},
}
EVEN = {"aerial": 1 / 3, "ground": 1 / 3, "race": 1 / 3}

# How well a marker's position suits marking an attacker who plays in a given position.
FIT: dict[Position, dict[Position, float]] = {
    Position.ST: {Position.CB: 1.0, Position.DM: 0.85, Position.FB: 0.7, Position.CM: 0.6},
    Position.AM: {Position.DM: 1.0, Position.CB: 0.85, Position.CM: 0.85, Position.FB: 0.6},
    Position.W: {Position.FB: 1.0, Position.CB: 0.75, Position.W: 0.65, Position.DM: 0.6},
    Position.CM: {Position.DM: 1.0, Position.CM: 0.95, Position.AM: 0.7, Position.CB: 0.65},
    Position.DM: {Position.CM: 1.0, Position.AM: 0.9, Position.DM: 0.9, Position.ST: 0.7},
    Position.FB: {Position.W: 1.0, Position.FB: 0.85, Position.CM: 0.6},
    Position.CB: {Position.ST: 1.0, Position.CB: 0.8, Position.DM: 0.6},
}
DEFAULT_FIT = 0.35
FOOT_BONUS = 0.04


def _kin(p: PlayerProfile, m: Modifiers, pos: tuple[float, float]) -> Kinematics:
    ph = p.physical
    return Kinematics(
        np.array([pos], float),
        np.zeros((1, 2)),
        np.array([ph.max_speed_ms * m.speed]),
        np.array([ph.accel_ms2 * m.accel]),
        np.array([ph.reaction_s * m.reaction]),
    )


def position_fit(marker: PlayerProfile, attacker: PlayerProfile) -> float:
    table = FIT.get(attacker.position, {})
    return max(table.get(p, DEFAULT_FIT) for p in [marker.position, *marker.positions])


def _foot_match(foot: Foot, channel: str) -> bool | None:
    if channel == "centre":
        return None
    return foot == Foot.BOTH or foot.value == channel


def _reasons(
    d: PlayerProfile, a: PlayerProfile, md: Modifiers, ma: Modifiers, fatigue: float
) -> list[str]:
    """Engine wording for what stands out about D against X (numbers straight from profiles)."""
    out = []
    reach = effective_reach_cm(d, md) - effective_reach_cm(a, ma)
    if abs(reach) >= 5:
        out.append(f"{reach:+.0f} cm reach")
    speed = d.physical.max_speed_ms * md.speed - a.physical.max_speed_ms * ma.speed
    if abs(speed) >= 0.2:
        out.append(f"{speed:+.1f} m/s top speed")
    tackle = d.skill.tackle - (a.skill.passing + a.skill.finishing) / 2
    if abs(tackle) >= 8:
        out.append(f"{tackle:+.0f} tackling vs his carrying")
    if fatigue >= 50:
        out.append(f"tired (fatigue {fatigue:.0f})")
    elif fatigue < 5:
        out.append("fresh legs")
    return out


def score_marker(
    attacker: PlayerProfile,
    att_mod: Modifiers,
    marker: PlayerProfile,
    mark_mod: Modifiers,
    fatigue: float,
    channel: str,
    on_pitch: bool,
) -> MarkerOption:
    a, d, ma, md = attacker, marker, att_mod, mark_mod
    p_air = 1.0 - aerial_win(
        _kin(a, ma, (-1.5, 0.6)),
        effective_reach_cm(a, ma),
        a.skill.aerial,
        _kin(d, md, (1.2, -0.6)),
        effective_reach_cm(d, md),
        d.skill.aerial,
        np.zeros(2),
        2.6,
        1.0,
    )
    p_race = recovery_run(_kin(d, md, (-4.0, 3.0)), _kin(a, ma, (0.0, 0.0)), np.array([25.0, 0.0]))
    p_ground = duel_success(
        d.skill.tackle, (a.skill.passing + a.skill.finishing) / 2, md.accel / ma.accel
    )
    w = WEIGHTS.get(a.archetype, EVEN)
    duel = w["aerial"] * p_air + w["ground"] * p_ground + w["race"] * p_race
    fit = position_fit(d, a)
    foot_ok = _foot_match(d.foot, channel)
    score = duel * (0.55 + 0.45 * fit) + (FOOT_BONUS if foot_ok else 0.0)
    reasons = _reasons(d, a, md, ma, fatigue)
    played = [
        p.value
        for p in d.positions
        if p != d.position and FIT.get(a.position, {}).get(p, 0) >= 0.85
    ]
    if played:
        reasons.append(f"has played {played[0]}")
    if foot_ok:
        reasons.append(f"{d.foot.value}-footed, suits the {channel} side")
    return MarkerOption(
        player_id=d.player_id,
        on_pitch=on_pitch,
        score=round(float(np.clip(score, 0.0, 1.0)), 4),
        aerial=round(float(p_air), 4),
        ground=round(float(p_ground), 4),
        race=round(float(p_race), 4),
        position_fit=round(fit, 2),
        foot=d.foot,
        foot_match=foot_ok,
        fatigue=round(fatigue, 1),
        reasons=reasons,
    )


def channel_of(y_rel: float) -> str:
    """Side of the pitch, seen by the defending team (attacking toward x = 105, left is y > 34)."""
    if y_rel > 44:
        return "left"
    if y_rel < 24:
        return "right"
    return "centre"


def best_markers(
    attacker_id: str,
    profiles: Mapping[str, PlayerProfile],
    modifiers: Mapping[str, Modifiers],
    fatigue: Mapping[str, float],
    candidates: Iterable[tuple[str, bool]],
    channel: str,
    t_ms: int,
    exclude: Iterable[str] = (),
    limit: int = 5,
) -> MarkingAdvice:
    """Rank `candidates` ((player id, on the pitch?) pairs) to mark `attacker_id`."""
    a = profiles[attacker_id]
    skip = set(exclude)
    rows = [
        score_marker(
            a,
            modifiers[attacker_id],
            profiles[pid],
            modifiers[pid],
            fatigue.get(pid, 0.0),
            channel,
            on,
        )
        for pid, on in candidates
        if pid not in skip and profiles[pid].position != Position.GK and pid != attacker_id
    ]
    rows.sort(key=lambda r: -r.score)
    return MarkingAdvice(
        attacker_id=attacker_id,
        t_ms=t_ms,
        channel=channel,
        weights=WEIGHTS.get(a.archetype, EVEN),
        options=rows[:limit],
        excluded=sorted(skip),
    )
