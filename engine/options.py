"""Option map: up to four things the player on the ball could have done.

Candidates: a pass to every outfield team-mate, a shot (inside 30 m), a cross (wide in the final
third) and a carry forward. Each gets p_success, an xT gain (threat after minus threat now) and a
Monte Carlo range. They are ranked by expected threat, p x max(xT gain, 0) plus a small safety
bonus, and the action actually taken is always kept so the board can show "chosen vs best".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from contracts import ActionKind, Event, EventType, Option, OptionSet, Point
from engine.montecarlo import REACTION_SD, RUNS, SPEED_SD, Evaluator, prob_range, seed_for
from engine.physics import Kinematics, pitch_control
from engine.probability import aerial_win, goal_geometry, pass_success, xg
from engine.profiles import effective_reach_cm
from engine.snapshot import Snapshot
from engine.xt import xt

MAX_OPTIONS = 4
CROSS_SPEED = 17.0  # m/s average, as the generator delivers crosses
CROSS_HEIGHT = 2.4  # m at the header


@dataclass
class _Cand:
    action: ActionKind
    target_id: str | None
    end: np.ndarray
    xt_gain: float
    fn: Evaluator

    def __post_init__(self) -> None:
        self.p = self.fn(None)

    @property
    def value(self) -> float:
        return self.p * max(self.xt_gain, 0.0) + 0.02 * self.p


def _jit(k: Kinematics, rng: np.random.Generator | None) -> Kinematics:
    return k if rng is None else k.jitter(rng, REACTION_SD, SPEED_SD)


def _pt(xy: np.ndarray) -> Point:
    return Point(
        x=round(float(np.clip(xy[0], -4.9, 109.9)), 2),
        y=round(float(np.clip(xy[1], -4.9, 72.9)), 2),
    )


def _pass_eval(
    start: np.ndarray,
    end: np.ndarray,
    recv: Kinematics,
    defs: Kinematics,
    passing: float,
    pressure: float,
) -> Evaluator:
    def fn(rng: np.random.Generator | None) -> float:
        return pass_success(
            start, end, _jit(recv, rng), _jit(defs, rng), passing=passing, pressure=pressure
        ).p

    return fn


def _shot_eval(dist: float, angle: float, pressure: float, finishing: float) -> Evaluator:
    def fn(rng: np.random.Generator | None) -> float:
        pr = pressure if rng is None else float(np.clip(pressure + rng.normal(0, 0.08), 0, 1))
        return xg(dist, angle, pr, False, finishing)

    return fn


def _cross_eval(
    snap: Snapshot, att: int, dfd: int, landing: np.ndarray, t_ball: float
) -> Evaluator:
    pa, pd = snap.profiles[snap.ids[att]], snap.profiles[snap.ids[dfd]]
    ra = effective_reach_cm(pa, snap.modifiers[snap.ids[att]])
    rd = effective_reach_cm(pd, snap.modifiers[snap.ids[dfd]])
    ka, kd = snap.kin([att]), snap.kin([dfd])

    def fn(rng: np.random.Generator | None) -> float:
        return aerial_win(
            _jit(ka, rng),
            ra,
            pa.skill.aerial,
            _jit(kd, rng),
            rd,
            pd.skill.aerial,
            landing,
            CROSS_HEIGHT,
            t_ball,
        )

    return fn


def _carry_eval(
    mine: Kinematics, theirs: Kinematics, end: np.ndarray, pressure: float
) -> Evaluator:
    def fn(rng: np.random.Generator | None) -> float:
        pc = pitch_control(_jit(mine, rng), _jit(theirs, rng), end[None, :])
        return float(pc[0]) * (1.0 - 0.5 * pressure)

    return fn


def candidates(
    snap: Snapshot, actor: str, pass_ends: dict[str, np.ndarray] | None = None
) -> list[_Cand]:
    """`pass_ends` pins a receiver's target point (the pass actually played goes where it went)."""
    team = snap.team_of(actor)
    start = snap.pos[snap.idx(actor)]
    fx, fy = (float(v) for v in snap.rel(team, start))
    here = xt(fx, fy)
    pressure = snap.pressure_on(actor)
    prof = snap.profiles[actor]
    opp = snap.opponents(actor)
    defs = snap.kin(opp)
    out: list[_Cand] = []

    for m in snap.team(team, outfield=True):
        mid = snap.ids[m]
        if mid == actor:
            continue
        end = (pass_ends or {}).get(mid)
        if end is None:
            end = np.clip(snap.pos[m] + snap.vel[m] * 0.6, [1.0, 1.0], [104.0, 67.0])
        ex, ey = snap.rel(team, end)
        fn = _pass_eval(start, end, snap.kin([m]), defs, prof.skill.passing, pressure)
        out.append(_Cand(ActionKind.PASS, mid, end, xt(ex, ey) - here, fn))

    dist, angle = goal_geometry(fx, fy)
    if dist < 30.0:
        fn = _shot_eval(dist, angle, pressure, prof.skill.finishing)
        goal = snap.rel(team, [105.0, 34.0])
        out.append(_Cand(ActionKind.SHOT, None, goal, fn(None) - here, fn))

    if fx > 72.0 and abs(fy - 34.0) > 14.0:
        landing = snap.rel(team, [95.0, 40.0 if fy < 34.0 else 28.0])
        mates = [m for m in snap.team(team, outfield=True) if snap.ids[m] != actor]
        defs_o = snap.opponents(actor, outfield=True)
        if mates and defs_o:
            am = min(mates, key=lambda m: float(np.linalg.norm(snap.pos[m] - landing)))
            dm = min(defs_o, key=lambda m: float(np.linalg.norm(snap.pos[m] - landing)))
            t_ball = float(np.linalg.norm(landing - start)) / CROSS_SPEED
            fn = _cross_eval(snap, am, dm, landing, t_ball)
            gain = 0.3 * xt(95.0, 34.0) - here
            out.append(_Cand(ActionKind.CROSS, snap.ids[am], landing, gain, fn))

    fwd = np.array([min(fx + 8.0, 103.0), fy + (34.0 - fy) * 0.15])
    carry_end = snap.rel(team, fwd)
    fn = _carry_eval(snap.kin(snap.team(team)), defs, carry_end, pressure)
    out.append(_Cand(ActionKind.CARRY, None, carry_end, xt(*fwd) - here, fn))
    return out


def _matches(c: _Cand, chosen: Event) -> bool:
    kind = {
        EventType.PASS: ActionKind.PASS,
        EventType.SHOT: ActionKind.SHOT,
        EventType.CROSS: ActionKind.CROSS,
        EventType.DRIBBLE: ActionKind.CARRY,
    }.get(chosen.type)
    if kind != c.action:
        return False
    return c.action != ActionKind.PASS or c.target_id == chosen.target_id


def option_set(
    snap: Snapshot,
    actor: str,
    moment_id: str,
    chosen: Event | None = None,
    runs: int = RUNS,
) -> OptionSet:
    pinned = {}
    if chosen is not None and chosen.type == EventType.PASS and chosen.target_id and chosen.end:
        pinned[chosen.target_id] = np.array([chosen.end.x, chosen.end.y])
    cands = sorted(candidates(snap, actor, pinned), key=lambda c: -c.value)
    picked = cands[:MAX_OPTIONS]
    if chosen is not None:
        match = next((c for c in cands if _matches(c, chosen)), None)
        if match is not None and match not in picked:
            picked = [*picked[: MAX_OPTIONS - 1], match]
    start = snap.pos[snap.idx(actor)]
    options = [
        Option(
            option_id=f"{moment_id}_opt{i + 1}",
            action=c.action,
            target_id=c.target_id,
            target=_pt(c.end),
            p_success=round(c.p, 4),
            range=prob_range(c.fn, seed_for(moment_id, c.action.value, c.target_id), runs),
            xt_gain=round(float(np.clip(c.xt_gain, -1.0, 1.0)), 4),
            path=[_pt(start), _pt(c.end)],
            chosen=chosen is not None and _matches(c, chosen),
        )
        for i, c in enumerate(picked)
    ]
    best = max(options, key=lambda o: o.p_success * max(o.xt_gain, 0.0) + 0.02 * o.p_success)
    return OptionSet(
        moment_id=moment_id,
        t_ms=snap.t_ms,
        actor_id=actor,
        options=options,
        best_option_id=best.option_id,
    )
