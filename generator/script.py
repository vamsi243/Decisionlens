"""Scripted key moments.

Each moment is a generator run by the simulator's director, one `yield` per 0.1 s tick. It
stops play with a restart near the scene, steers the players involved, and forces the outcome.
The key event of every moment carries the tags `scripted` and `scripted:<moment type>` so the
Phase 3 detector can be scored against ground truth.

All coordinates below are absolute: Riverside (home) attacks toward x = 105, Hillton toward x = 0.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from contracts import EventType, MomentType, Outcome
from generator.roster import AWAY, HOME
from generator.sim import OWNED, MatchSim, Script


def _tags(kind: MomentType, *extra: str) -> tuple[str, ...]:
    return (*extra, "scripted", f"scripted:{kind.value}")


def line_breaking_pass(sim: MatchSim) -> Script:
    """Riverside's deep playmaker splits Hillton's midfield to find the striker between lines."""
    cb, dm, st = sim.pid("RIV_04"), sim.pid("RIV_06"), sim.pid("RIV_09")
    sim.override(dm, (38, 37))
    sim.override(st, (74, 33))
    yield from sim.scripted_restart(HOME, (33, 30), cb, wait_s=4)
    yield from sim.wait(0.8)
    yield from sim.scripted_pass(cb, dm, True, end=(38, 37))
    yield from sim.wait(1.0)
    sim.override(st, (76, 33))
    yield from sim.scripted_pass(
        dm,
        st,
        True,
        end=(76, 33),
        lofted=False,
        tags=_tags(MomentType.LINE_BREAKING_PASS, "line_breaking", "progressive"),
    )
    yield from sim.wait(1.0)


def press_turnover(sim: MatchSim) -> Script:
    """Hillton's high press forces a loose pass out of Riverside's centre-back."""
    gk, cb, dm = sim.pid("RIV_01"), sim.pid("RIV_05"), sim.pid("RIV_06")
    h_st, h_am, h_lw = sim.pid("HIL_09"), sim.pid("HIL_10"), sim.pid("HIL_11")
    sim.override(cb, (13, 22))
    sim.override(dm, (24, 34))
    sim.override(h_st, (26, 30))
    sim.override(h_am, (27, 36))
    sim.override(h_lw, (24, 14))
    yield from sim.scripted_restart(HOME, (5.5, 34), gk, wait_s=5)
    yield from sim.wait(0.6)
    yield from sim.scripted_pass(gk, cb, True, end=(13, 22))
    sim.override(h_st, lambda: sim.pos[cb] + np.array([1.0, 0.8]))
    sim.override(h_lw, lambda: sim.pos[cb] + np.array([0.5, -2.0]))
    sim.override(h_am, (19, 28))
    yield from sim.until(lambda: float(np.linalg.norm(sim.pos[h_st] - sim.pos[cb])) < 2.0, 3.0)
    sim.overrides.pop(dm, None)
    yield from sim.scripted_pass(
        cb,
        dm,
        False,
        interceptor=h_am,
        lofted=False,
        tags=_tags(MomentType.PRESS_TURNOVER, "high_press"),
    )
    yield from sim.wait(1.0)


def big_chance(sim: MatchSim) -> Script:
    """A through ball sends Riverside's striker clean through; he drags it wide from 11 m."""
    cm, st = sim.pid("RIV_08"), sim.pid("RIV_09")
    sim.override(st, (80, 36))
    yield from sim.scripted_restart(HOME, (62, 30), cm, wait_s=4)
    yield from sim.wait(0.5)
    sim.override(st, (93, 35))
    yield from sim.wait(0.5)
    hil = sim.on_team(AWAY, outfield=True)
    sim.press_block[hil] = sim.t + 6.0  # the back line is caught square: nobody gets close
    yield from sim.scripted_pass(cm, st, True, end=(91, 35), lofted=False, tags=("through_ball",))
    sim.override(st, (95, 34.5), urgent=False)
    yield from sim.wait(0.5)
    sim._shoot(
        st,
        sim.pressure_on(st),
        goal=False,
        miss="wide",
        tags=_tags(MomentType.BIG_CHANCE, "big_chance"),
    )
    yield from sim.until(lambda: sim.mode != OWNED and sim.flight is None, 4)
    yield from sim.wait(0.5)


def recovery_run(sim: MatchSim) -> Script:
    """Riverside's overlapping left-back is caught upfield; Hillton's winger wins the race."""
    cm, lb = sim.pid("RIV_10"), sim.pid("RIV_03")
    h_rb, h_rw = sim.pid("HIL_02"), sim.pid("HIL_07")
    sim.override(lb, (67, 62))
    sim.override(h_rb, (64, 59))
    sim.override(h_rw, (50, 57))
    yield from sim.scripted_restart(HOME, (60, 48), cm, wait_s=4)
    yield from sim.wait(1.2)
    yield from sim.scripted_pass(cm, lb, False, end=(68, 61), interceptor=h_rb, lofted=False)
    sim.override(h_rw, (33, 57))
    sim.override(lb, lambda: sim.pos[h_rw])
    yield from sim.wait(0.3)
    yield from sim.scripted_pass(h_rb, h_rw, True, end=(35, 57), lofted=True, tags=("counter",))
    sim.override(h_rw, (17, 50), urgent=False)
    yield from sim.until(lambda: sim.pos[h_rw][0] < 24.0, 6)
    sim.emit(
        EventType.DRIBBLE,
        team_id=AWAY,
        player_id=h_rw,
        target_id=lb,
        start=sim.pos[h_rw].copy(),
        outcome=Outcome.SUCCESS,
        tags=list(_tags(MomentType.RECOVERY_RUN, "recovery_run")),
    )
    yield from sim.wait(0.8)


def aerial_duel(sim: MatchSim) -> Script:
    """Late cross to the back post: Hillton's target man out-jumps Riverside's right-back."""
    rw, st, rb = sim.pid("HIL_07"), sim.pid("HIL_09"), sim.pid("RIV_02")
    sim.override(st, (9, 29))
    sim.override(rb, (8, 27))
    yield from sim.scripted_restart(AWAY, (22, 62), rw, wait_s=5)
    yield from sim.wait(0.8)
    landing = np.array([5.6, 27.2])
    sim.override(st, landing + np.array([0.6, 0.4]))
    sim.override(rb, landing + np.array([-0.5, -0.4]))
    sim._delivery(
        rw,
        st,
        rb,
        landing,
        att_wins=True,
        pressure=sim.pressure_on(rw),
        tags=("back_post",),
        duel_tags=_tags(MomentType.AERIAL_DUEL, "back_post"),
        header_goal=True,
    )
    yield from sim.until(lambda: sim.flight is None or sim.flight.kind == "shot", 5)
    sim.overrides.clear()
    yield from sim.until(lambda: sim.flight is None, 3)
    yield from sim.wait(0.5)


@dataclass(frozen=True)
class ScriptedMoment:
    kind: MomentType
    minute: float
    run: Callable[[MatchSim], Script]

    @property
    def start_s(self) -> float:
        return self.minute * 60.0


SCRIPTED_MOMENTS = [
    ScriptedMoment(MomentType.LINE_BREAKING_PASS, 23.0, line_breaking_pass),
    ScriptedMoment(MomentType.PRESS_TURNOVER, 38.0, press_turnover),
    ScriptedMoment(MomentType.BIG_CHANCE, 57.0, big_chance),
    ScriptedMoment(MomentType.RECOVERY_RUN, 71.0, recovery_run),
    ScriptedMoment(MomentType.AERIAL_DUEL, 86.0, aerial_duel),
]

# (minute, out, in): substitutions keep every player in a scripted moment on the pitch, and
# leave a fresh aerial CB (RIV_14) and full-back (RIV_15) on the bench for what-if swaps.
SUBSTITUTIONS = [
    (60.0, "HIL_10", "HIL_16"),
    (62.0, "RIV_08", "RIV_16"),
    (70.0, "HIL_11", "HIL_17"),
    (74.0, "RIV_09", "RIV_17"),
]
KNOCKS = [(64.0, "HIL_08")]


def install(sim: MatchSim) -> None:
    """Register scripted moments, substitutions and knocks on a simulator."""
    full = sim.period_s >= 45 * 60
    if full:
        sim.director = [(m.start_s, m.run) for m in SCRIPTED_MOMENTS]
        sim.subs = [(m * 60.0, sim.pid(a), sim.pid(b)) for m, a, b in SUBSTITUTIONS]
        sim.knocks = [(m * 60.0, sim.pid(p)) for m, p in KNOCKS]
