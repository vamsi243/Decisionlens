"""Evaluate the probability at the heart of a key moment, from the actor's point of view.

A `MomentSpec` pins down the question ("does RIV_02 win this header?") and the frame to ask it
at; `evaluate` answers it, optionally with a different player profile swapped in and with
jittered kinematics for Monte Carlo ranges.

| Moment             | Actor          | Probability                                   |
| ------------------ | -------------- | --------------------------------------------- |
| aerial_duel        | defender       | 1 - aerial_win(attacker), asked at the cross  |
| recovery_run       | chasing player | recovery_run, asked when the carrier receives |
| big_chance         | shooter        | xG at the shot                                |
| line_breaking_pass | passer         | pass_success at the kick                      |
| press_turnover     | passer         | pass_success at the kick                      |
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from contracts import Event, EventType, MomentType
from engine.montecarlo import REACTION_SD, SPEED_SD
from engine.physics import Kinematics
from engine.probability import aerial_win, goal_geometry, pass_success, recovery_run, xg
from engine.profiles import effective_reach_cm
from engine.snapshot import Replacement, Snapshot

PASS_MOMENTS = {MomentType.LINE_BREAKING_PASS, MomentType.PRESS_TURNOVER}


@dataclass(frozen=True)
class MomentSpec:
    kind: MomentType
    frame: int  # frame to evaluate at
    actor_id: str  # the player whose action / duel the probability is about
    opponent_id: str | None = None
    target_id: str | None = None
    point: tuple[float, float] | None = None  # landing / pass end / danger point
    ball_height_m: float = 0.0
    t_ball: float = 0.0  # seconds until the ball arrives at `point`
    header: bool = False


def _j(k: Kinematics, rng: np.random.Generator | None) -> Kinematics:
    return k if rng is None else k.jitter(rng, REACTION_SD, SPEED_SD)


def evaluate(
    snap: Snapshot,
    spec: MomentSpec,
    replace: Mapping[str, Replacement] | None = None,
    rng: np.random.Generator | None = None,
) -> float:
    replace = replace or {}
    actor = spec.actor_id

    if spec.kind == MomentType.AERIAL_DUEL:
        assert spec.opponent_id and spec.point
        att_id, dfd_id = spec.opponent_id, actor
        att = _j(snap.kin([snap.idx(att_id)], replace), rng)
        dfd = _j(snap.kin([snap.idx(dfd_id)], replace), rng)
        pa, ma = replace.get(att_id, (snap.profiles[att_id], snap.modifiers[att_id]))
        pd, md = replace.get(dfd_id, (snap.profiles[dfd_id], snap.modifiers[dfd_id]))
        p_att = aerial_win(
            att,
            effective_reach_cm(pa, ma),
            pa.skill.aerial,
            dfd,
            effective_reach_cm(pd, md),
            pd.skill.aerial,
            np.array(spec.point),
            spec.ball_height_m,
            spec.t_ball,
        )
        return 1.0 - p_att

    if spec.kind == MomentType.RECOVERY_RUN:
        assert spec.opponent_id
        chaser = _j(snap.kin([snap.idx(actor)], replace), rng)
        carrier = _j(snap.kin([snap.idx(spec.opponent_id)], replace), rng)
        point = spec.point or danger_point(snap, spec.opponent_id)
        return recovery_run(chaser, carrier, np.array(point))

    if spec.kind == MomentType.BIG_CHANCE:
        p, _ = replace.get(actor, (snap.profiles[actor], snap.modifiers[actor]))
        team = snap.team_of(actor)
        x, y = snap.rel(team, snap.pos[snap.idx(actor)])
        dist, angle = goal_geometry(float(x), float(y))
        pressure = snap.pressure_on(actor)
        if rng is not None:
            pressure = float(np.clip(pressure + rng.normal(0.0, 0.08), 0.0, 1.0))
        return xg(dist, angle, pressure, spec.header, p.skill.finishing)

    if spec.kind in PASS_MOMENTS:
        assert spec.target_id and spec.point
        p, _ = replace.get(actor, (snap.profiles[actor], snap.modifiers[actor]))
        recv = _j(snap.kin([snap.idx(spec.target_id)], replace), rng)
        defenders = _j(snap.kin(snap.opponents(actor), replace), rng)
        return pass_success(
            snap.pos[snap.idx(actor)],
            np.array(spec.point),
            recv,
            defenders,
            passing=p.skill.passing,
            pressure=snap.pressure_on(actor),
        ).p

    raise ValueError(f"no evaluator for {spec.kind}")


def danger_point(snap: Snapshot, carrier_id: str) -> tuple[float, float]:
    """Where the carrier is heading: the edge of the box, level with him (team-relative)."""
    team = snap.team_of(carrier_id)
    _, y = snap.rel(team, snap.pos[snap.idx(carrier_id)])
    target = np.array([88.5, float(np.clip(y, 20.0, 48.0))])
    x2, y2 = snap.rel(team, target)
    return float(x2), float(y2)


def spec_for_event(
    kind: MomentType, event: Event, events: list[Event], owner_frame: int | None = None
) -> MomentSpec:
    """Build the spec for a key event. `owner_frame`: when the carrier got the ball (recovery)."""
    assert event.player_id
    if kind == MomentType.AERIAL_DUEL:
        cross = next(
            e
            for e in reversed(events)
            if e.t_ms <= event.t_ms and e.type == EventType.CROSS and e.event_id < event.event_id
        )
        assert event.start
        return MomentSpec(
            kind,
            frame=cross.frame_ref,
            actor_id=event.player_id,
            opponent_id=event.target_id,
            point=(event.start.x, event.start.y),
            ball_height_m=event.ball_height_m or 2.4,
            t_ball=(event.t_ms - cross.t_ms) / 1000.0,
        )
    if kind == MomentType.RECOVERY_RUN:
        # The dribble event names the carrier (player) and the chaser (target).
        assert event.target_id
        return MomentSpec(
            kind,
            frame=owner_frame if owner_frame is not None else event.frame_ref,
            actor_id=event.target_id,
            opponent_id=event.player_id,
        )
    if kind == MomentType.BIG_CHANCE:
        return MomentSpec(
            kind, frame=event.frame_ref, actor_id=event.player_id, header="header" in event.tags
        )
    if kind in PASS_MOMENTS:
        assert event.end and event.target_id
        return MomentSpec(
            kind,
            frame=event.frame_ref,
            actor_id=event.player_id,
            target_id=event.target_id,
            point=(event.end.x, event.end.y),
        )
    raise ValueError(f"no spec builder for {kind}")
