"""10 Hz match simulator.

The model is deliberately simple but football-shaped:

* every player has a formation slot; the team block slides toward the ball, pushes up and
  widens in possession, drops and narrows out of it;
* in possession, runners (wingers, forwards, overlapping full-backs) make forward runs;
* out of possession the nearest one or two players press the ball;
* the ball carrier decides every 0.5-2 s between pass, cross, shot, clearance or carrying on;
  outcomes are sampled from `generator.rules` at the moment of the kick, so the event log and
  the ball flight always agree;
* the ball flies with exponential drag and a parabolic arc for lofted balls and crosses;
* fatigue builds with high-speed running and slows players down.

A director runs scripted key moments (see `generator.script`) as Python generators that
override targets and force outcomes for a few seconds.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np

from contracts import Archetype, Event, EventType, Outcome, Period, Point
from engine import probability as P
from engine.fatigue import FatigueModel
from engine.physics import LOFT_DISTANCE, Kinematics, flight_params
from engine.profiles import effective_reach_cm
from generator.roster import AWAY, HOME, WORK_RATE, Roster

HZ = 10
DT = 1.0 / HZ
L, W = 105.0, 68.0
BALL_R = 0.11

OWNED, FLIGHT, LOOSE, DEAD = range(4)

Script = Generator[None, None, None]
Target = np.ndarray | tuple[float, float] | Callable[[], np.ndarray]

RUN_RATE = {  # forward runs per second while in possession
    Archetype.OVERLAPPING_FB: 0.018,
    Archetype.WINGER: 0.035,
    Archetype.PRESSING_FORWARD: 0.035,
    Archetype.TARGET_MAN: 0.02,
    Archetype.BOX_TO_BOX: 0.014,
    Archetype.DEEP_PLAYMAKER: 0.005,
}
DUEL_HAZARD = 0.25  # challenges per second while a defender is within 1.5 m
DRIBBLERS = {Archetype.WINGER, Archetype.PRESSING_FORWARD, Archetype.OVERLAPPING_FB}


def rel(team: int, xy: np.ndarray) -> np.ndarray:
    """Absolute <-> team-relative (an involution: the away team is mirrored on both axes)."""
    return xy if team == HOME else np.array([L, W]) - xy


def _seg_dist(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Distance from points p (n,2) to segment a-b and the projection fraction."""
    ab = b - a
    denom = float(ab @ ab) or 1e-9
    u = np.clip(((p - a) @ ab) / denom, 0.0, 1.0)
    proj = a + u[:, None] * ab
    return np.linalg.norm(p - proj, axis=1), u


@dataclass
class Flight:
    kind: str
    start: np.ndarray
    end: np.ndarray
    t0: float
    T: float
    peak: float
    z_end: float
    k: float
    on_arrive: Callable[[], None]

    def at(self, t: float) -> tuple[np.ndarray, float, bool]:
        u = min(1.0, (t - self.t0) / self.T)
        s = (1 - math.exp(-self.k * self.T * u)) / (1 - math.exp(-self.k * self.T))
        xy = self.start + (self.end - self.start) * s
        z = 4 * self.peak * u * (1 - u) + self.z_end * u + BALL_R * (1 - u)
        return xy, z, u >= 1.0

    @property
    def v0(self) -> float:
        d = float(np.linalg.norm(self.end - self.start))
        return d * self.k / (1 - math.exp(-self.k * self.T))


@dataclass
class Restart:
    team: int
    spot: np.ndarray
    actor: int
    ready_at: float
    kickoff: bool = False


class MatchSim:
    def __init__(self, roster: Roster, seed: int, period_s: float = 45 * 60) -> None:
        self.roster = roster
        self.rng = np.random.default_rng(seed)
        self.period_s = period_s
        ps = roster.players
        self.n = n = len(ps)
        self.ids = [p.id for p in ps]
        self.index = {pid: i for i, pid in enumerate(self.ids)}
        self.profiles = [p.profile for p in ps]
        self.team = np.array([p.team for p in ps])
        self.on = np.array([p.slot is not None for p in ps])
        self.is_gk = np.array([p.profile.archetype == Archetype.GOALKEEPER for p in ps])
        self.vmax = np.array([p.profile.physical.max_speed_ms for p in ps])
        self.acc = np.array([p.profile.physical.accel_ms2 for p in ps])
        self.react = np.array([p.profile.physical.reaction_s for p in ps])
        self.aerial = np.array([p.profile.skill.aerial for p in ps])
        self.tackle = np.array([p.profile.skill.tackle for p in ps])
        self.carry_skill = np.array(
            [(p.profile.skill.passing + p.profile.skill.finishing) / 2 for p in ps]
        )
        self.passing = np.array([p.profile.skill.passing for p in ps])
        self.run_rate = np.array(
            [RUN_RATE.get(p.profile.archetype, 0.0) * WORK_RATE.get(p.id, 1.0) for p in ps]
        )
        self.overlapper = np.array([p.profile.archetype == Archetype.OVERLAPPING_FB for p in ps])
        self.base = np.array(
            [roster.formation(p.team)[p.slot] if p.slot else (50.0, 34.0) for p in ps], float
        )
        self.phase = self.rng.uniform(0, 2 * math.pi, (n, 2))

        self.pos = np.zeros((n, 2))
        self.shape = np.zeros((n, 2))  # low-pass filtered shape targets
        self.vel = np.zeros((n, 2))
        self.fm = FatigueModel(n)  # the engine's fatigue model: same maths the app explains
        self.run_until = np.zeros(n)
        self.run_target = np.zeros((n, 2))
        self.press_block = np.zeros(n)

        self.t = 0.0
        self.frame = 0
        self.period = Period.FIRST_HALF
        self.ball = np.array([L / 2, W / 2, BALL_R])
        self.ball_v = np.zeros(2)
        self.mode = DEAD
        self.owner = -1
        self.poss_team = HOME
        self.last_touch_team = HOME
        self.hold_until = 0.0
        self.flight: Flight | None = None
        self.flight_roles: list[tuple[int, np.ndarray]] = []
        self.restart: Restart | None = None
        self.loose_since = 0.0
        # A pass's outcome is decided at the kick; if the ball runs loose afterwards only the
        # team that "won" it may collect, so the event log and tracking always agree.
        self.loose_claim: int | None = None
        self.loose_intercept = False
        self.last_pressure: dict[int, float] = {}
        self.score = [0, 0]

        self.scripted = False
        self.overrides: dict[int, tuple[Target, bool]] = {}
        self.director: list[tuple[float, Callable[[MatchSim], Script]]] = []
        # Spells of pressure (start_s, end_s, team): big moments come in intense spells, so the
        # attacking side runs and shoots more and duels are fiercer around scripted moments.
        self.spells: list[tuple[float, float, int]] = []
        self.active: Script | None = None
        self.subs: list[tuple[float, int, int]] = []  # (time_s, out, in)
        self.knocks: list[tuple[float, int]] = []
        self.events: list[Event] = []

    # ------------------------------------------------------------------ helpers
    def pid(self, player_id: str) -> int:
        return self.index[player_id]

    def on_team(self, team: int, outfield: bool = False) -> np.ndarray:
        mask = self.on & (self.team == team)
        if outfield:
            mask &= ~self.is_gk
        return np.flatnonzero(mask)

    @property
    def fatigue(self) -> np.ndarray:
        return self.fm.fatigue

    def spell_team(self) -> int:
        """Team on top in the current spell of pressure, or -1."""
        return next((tm for a, b, tm in self.spells if a <= self.t < b), -1)

    def speed_mod(self) -> np.ndarray:
        return self.fm.speed_mod()

    def kin(self, idx: np.ndarray | list[int]) -> Kinematics:
        """Engine kinematics for players `idx`, scaled by their current fatigue."""
        ix = np.asarray(idx, int)
        return Kinematics(
            pos=self.pos[ix],
            vel=self.vel[ix],
            vmax=(self.vmax * self.fm.speed_mod())[ix],
            accel=(self.acc * self.fm.accel_mod())[ix],
            reaction=(self.react * self.fm.reaction_mod())[ix],
        )

    def reach(self, i: int) -> float:
        return effective_reach_cm(self.profiles[i], self.fm.modifiers(i))

    def nearest(self, idx: np.ndarray, xy: np.ndarray) -> tuple[int, float]:
        d = np.linalg.norm(self.pos[idx] - xy, axis=1)
        k = int(np.argmin(d))
        return int(idx[k]), float(d[k])

    def pressure_on(self, i: int) -> float:
        _, d = self.nearest(self.on_team(1 - self.team[i]), self.pos[i])
        return P.pressure_from_distance(d)

    def gk_of(self, team: int) -> int:
        return int(self.on_team(team)[self.is_gk[self.on_team(team)]][0])

    def emit(self, etype: EventType, **f: Any) -> Event:
        for key in ("start", "end"):
            if isinstance(f.get(key), np.ndarray):
                xy = f[key]
                f[key] = Point(
                    x=round(float(np.clip(xy[0], -4.9, L + 4.9)), 2),
                    y=round(float(np.clip(xy[1], -4.9, W + 4.9)), 2),
                )
        for key in ("player_id", "target_id"):
            if isinstance(f.get(key), (int, np.integer)):
                f[key] = self.ids[int(f[key])]
        if isinstance(f.get("team_id"), (int, np.integer)):
            f["team_id"] = self.roster.meta.teams[int(f["team_id"])].team_id
        for key in ("ball_speed_ms", "ball_height_m", "pressure"):
            if f.get(key) is not None:
                f[key] = round(float(f[key]), 3)
        ev = Event(
            event_id=f"ev_{len(self.events):06d}",
            t_ms=round(self.t * 1000),
            period=self.period,
            type=etype,
            frame_ref=self.frame,
            **f,
        )
        self.events.append(ev)
        return ev

    # ------------------------------------------------------------------ main loop
    def run(self, on_frame: Callable[[MatchSim], object]) -> None:
        for period, kicker_team in ((Period.FIRST_HALF, HOME), (Period.SECOND_HALF, AWAY)):
            self.period = period
            first = 0 if period == Period.FIRST_HALF else round(self.period_s * HZ)
            self.frame = first
            self.t = first / HZ
            self._kickoff_teleport(kicker_team)
            self.emit(EventType.PERIOD_START)
            for f in range(first, first + round(self.period_s * HZ)):
                self.frame = f
                self.t = f / HZ
                self.step()
                on_frame(self)
            self.emit(EventType.PERIOD_END)

    def step(self) -> None:
        self._run_director()
        if self.mode == OWNED and not self.scripted and self.pressure_on(self.owner) > 0.85:
            self.hold_until = min(self.hold_until, self.t + 0.7)  # heavily pressed: release
        if self.mode == OWNED and not self.scripted and self.t >= self.hold_until:
            self._decide()
        targets, caps = self._targets()
        self._move(targets, caps)
        self._update_ball()
        if self.mode == OWNED and not self.scripted:
            self._duels()
        self._pressure_events()
        self._update_fatigue()
        self._substitutions()

    # ------------------------------------------------------------------ director
    def _run_director(self) -> None:
        if self.active is None and self.director and self.t >= self.director[0][0]:
            _, factory = self.director.pop(0)
            self.active = factory(self)
            self.scripted = True
        if self.active is not None:
            try:
                next(self.active)
            except StopIteration:
                self.active = None
                self.scripted = False
                self.overrides.clear()
                self.hold_until = min(self.hold_until, self.t + 0.5)

    def wait(self, seconds: float) -> Iterator[None]:
        end = self.t + seconds - 1e-9
        while self.t < end:
            yield

    def until(self, cond: Callable[[], bool], timeout: float = 20.0) -> Iterator[None]:
        end = self.t + timeout
        while not cond() and self.t < end:
            yield

    def override(self, i: int, target: Target, urgent: bool = True) -> None:
        self.overrides[i] = (target if callable(target) else np.asarray(target, float), urgent)

    def scripted_restart(
        self, team: int, spot: tuple[float, float], actor: int, wait_s: float
    ) -> Iterator[None]:
        """Stop play (a foul if the ball was live) and restart with `actor` on the ball."""
        if self.mode in (OWNED, FLIGHT, LOOSE):
            fouler, _ = self.nearest(self.on_team(1 - team, outfield=True), self.ball[:2])
            fouled, _ = self.nearest(self.on_team(team, outfield=True), self.ball[:2])
            self.emit(
                EventType.FOUL,
                team_id=1 - team,
                player_id=fouler,
                target_id=fouled,
                start=self.ball[:2].copy(),
                tags=["stoppage"],
            )
        self.begin_dead(team, np.array(spot, float), actor, wait_s)
        yield from self.until(lambda: self.mode == OWNED and self.owner == actor, wait_s + 12)
        if not (self.mode == OWNED and self.owner == actor):  # safety net, should not trigger
            self.pos[actor] = self.restart.spot if self.restart else self.pos[actor]
            self._gain(actor)
        self.hold_until = self.t + 1e9  # script decides the next action

    def scripted_pass(
        self,
        passer: int,
        receiver: int,
        success: bool,
        *,
        end: tuple[float, float] | None = None,
        interceptor: int | None = None,
        lofted: bool | None = None,
        tags: tuple[str, ...] = (),
    ) -> Iterator[None]:
        self._pass(
            passer,
            receiver,
            success,
            end=None if end is None else np.array(end, float),
            interceptor=interceptor,
            lofted=lofted,
            tags=tags,
        )
        yield
        yield from self.until(lambda: self.mode == OWNED, 8)
        self.hold_until = self.t + 1e9

    # ------------------------------------------------------------------ restarts
    def _kickoff_spots(self, team: int, kicker_team: int) -> np.ndarray:
        idx = self.on_team(team)
        fx = np.minimum(self.base[idx, 0] * 0.85, 48.0 if team == kicker_team else 43.0)
        fy = self.base[idx, 1]
        fx[self.is_gk[idx]] = 4.0
        return np.array([rel(team, np.array(p)) for p in zip(fx, fy, strict=True)])

    def _kicker(self, team: int) -> int:
        idx = self.on_team(team, outfield=True)
        return int(idx[np.argmax(self.base[idx, 0])])

    def _kickoff_teleport(self, kicker_team: int) -> None:
        for team in (HOME, AWAY):
            idx = self.on_team(team)
            self.pos[idx] = self._kickoff_spots(team, kicker_team)
            self.shape[idx] = self.pos[idx]
            self.vel[idx] = 0
        k = self._kicker(kicker_team)
        self.pos[k] = [L / 2 - 0.6 * (1 if kicker_team == HOME else -1), W / 2]
        self.ball[:] = [L / 2, W / 2, BALL_R]
        self.restart = None
        self.flight = None
        if not self.scripted:
            self.overrides.clear()
        self._gain(k, quiet=True)
        self.hold_until = self.t + 1.0

    def begin_dead(
        self, team: int, spot: np.ndarray, actor: int, wait_s: float, kickoff: bool = False
    ) -> None:
        self.mode = DEAD
        self.flight = None
        self.owner = -1
        self.poss_team = team
        self.restart = Restart(team, spot, actor, self.t + wait_s, kickoff)

    def _gain(self, i: int, quiet: bool = False) -> None:
        team = int(self.team[i])
        changed = team != self.poss_team
        self.owner = i
        self.mode = OWNED
        self.flight = None
        self.flight_roles = []
        self.restart = None
        self.loose_claim = None
        self.loose_intercept = False
        self.ball_v[:] = 0
        self.last_touch_team = team
        lo, hi = (2.0, 4.0) if self.is_gk[i] else (1.0, 3.2)
        self.hold_until = self.t + float(self.rng.uniform(lo, hi))
        if changed:
            self.poss_team = team
            self.run_until[self.team != team] = 0
            if not quiet:
                self.emit(
                    EventType.POSSESSION_CHANGE,
                    team_id=team,
                    player_id=i,
                    start=self.pos[i].copy(),
                )

    # ------------------------------------------------------------------ targets & motion
    def _targets(self) -> tuple[np.ndarray, np.ndarray]:
        targets = self.pos.copy()
        urgent = np.zeros(self.n, bool)
        ball_ref = self.restart.spot if self.mode == DEAD and self.restart else self.ball[:2]
        draws = self.rng.random((self.n, 4))
        kickoff_for = (
            self.restart.team if self.mode == DEAD and self.restart and self.restart.kickoff else -1
        )

        for team in (HOME, AWAY):
            idx = self.on_team(team)
            if kickoff_for >= 0:
                targets[idx] = self._kickoff_spots(team, kickoff_for)
                continue
            bx, by = rel(team, ball_ref)
            in_poss = self.poss_team == team
            bfx, bfy = self.base[idx, 0], self.base[idx, 1]
            fx = bfx + 0.5 * (bx - 50.0) + (6.0 if in_poss else -5.0)
            if not in_poss:  # stay goal-side of the ball
                fx = np.minimum(fx, bx + (bfx - 25.0) * 0.6 - 2.0)
            fy = (
                34.0
                + (bfy - 34.0) * (1.05 if in_poss else 0.72)
                + (by - 34.0) * (0.22 if in_poss else 0.35)
            )
            fx = np.clip(fx, 6.0, 92.0) + 1.8 * np.sin(0.29 * self.t + self.phase[idx, 0])
            fy = np.clip(fy, 2.0, 66.0) + 1.8 * np.sin(0.21 * self.t + self.phase[idx, 1])
            gk = self.is_gk[idx]
            fx[gk] = 4.0 + np.clip(bx - 30.0, 0.0, 50.0) * 0.07
            fy[gk] = 34.0 + (by - 34.0) * 0.18
            targets[idx] = np.stack([fx, fy], 1) if team == HOME else np.stack([L - fx, W - fy], 1)

            if in_poss and self.mode in (OWNED, FLIGHT):
                self._start_runs(team, idx, bx, draws)
                running = idx[(self.run_until[idx] > self.t) & (idx != self.owner)]
                targets[running] = self.run_target[running]
                urgent[running] = True

        # Players react to the block moving with the ball over ~1.5 s, not instantly.
        alpha = DT / 1.5
        moved = ~urgent
        self.shape[moved] += (targets[moved] - self.shape[moved]) * alpha
        self.shape[urgent] = targets[urgent]
        targets = self.shape.copy()

        if self.mode == OWNED:
            o = self.owner
            team = int(self.team[o])
            ox, oy = rel(team, self.pos[o])
            targets[o] = rel(team, np.array([min(ox + 7.0, 103.0), oy + (34.0 - oy) * 0.15]))
            self._pressers(o, targets, urgent)
        elif self.mode == FLIGHT:
            for i, pt in self.flight_roles:
                targets[i] = pt
                urgent[i] = True
        elif self.mode == LOOSE:
            aim = self.ball[:2] + self.ball_v * 0.5
            teams = (HOME, AWAY) if self.loose_claim is None else (self.loose_claim,)
            for team in teams:
                i, _ = self.nearest(self.on_team(team, outfield=True), self.ball[:2])
                targets[i] = aim
                urgent[i] = True
        elif self.mode == DEAD and self.restart:
            targets[self.restart.actor] = self.restart.spot
            urgent[self.restart.actor] = True

        for i, (tgt, urg) in self.overrides.items():
            if self.on[i] and not (self.mode == OWNED and i == self.owner and not urg):
                targets[i] = tgt() if callable(tgt) else tgt
                urgent[i] = urgent[i] or urg

        vmax = self.vmax * self.speed_mod()
        dist = np.linalg.norm(targets - self.pos, axis=1)
        jog = np.minimum(vmax, np.minimum(0.6 + 0.4 * dist, 4.5))
        caps = np.where(urgent, vmax * 0.9, np.where(dist > 15.0, vmax * 0.75, jog))
        if self.mode == OWNED:  # carry faster into open space, shield under pressure
            o = self.owner
            caps[o] = vmax[o] * (0.4 + 0.35 * (1.0 - self.pressure_on(o)))
        return targets, caps

    def _start_runs(self, team: int, idx: np.ndarray, bx: float, draws: np.ndarray) -> None:
        rate = self.run_rate[idx] * np.where(self.overlapper[idx] & (bx > 45.0), 2.0, 1.0)
        if self.spell_team() == team:
            rate = rate * 3.0
        start = (self.run_until[idx] <= self.t) & (draws[idx, 0] < rate * DT) & (idx != self.owner)
        for i in idx[start]:
            fx = min(bx + 10.0 + 14.0 * draws[i, 1], 93.0)
            if self.overlapper[i]:
                fy = 4.0 if self.base[i, 1] < 34 else 64.0
            else:
                fy = float(np.clip(self.base[i, 1] + (draws[i, 2] - 0.5) * 16.0, 3.0, 65.0))
            self.run_target[i] = rel(team, np.array([fx, fy]))
            self.run_until[i] = self.t + 2.5 + 2.0 * draws[i, 3]

    def _pressers(self, o: int, targets: np.ndarray, urgent: np.ndarray) -> None:
        dteam = 1 - int(self.team[o])
        idx = self.on_team(dteam, outfield=True)
        idx = idx[self.press_block[idx] <= self.t]
        if len(idx) == 0:
            return
        d = np.linalg.norm(self.pos[idx] - self.pos[o], axis=1)
        order = idx[np.argsort(d, kind="stable")]
        targets[order[0]] = self.pos[o]
        urgent[order[0]] = True
        bx_d = rel(dteam, self.pos[o])[0]
        if len(order) > 1 and bx_d < 60.0:
            goal = rel(dteam, np.array([0.0, 34.0]))
            cover = (
                self.pos[o]
                + (goal - self.pos[o]) / max(1e-6, float(np.linalg.norm(goal - self.pos[o]))) * 4.0
            )
            targets[order[1]] = cover
            urgent[order[1]] = True

    def _move(self, targets: np.ndarray, caps: np.ndarray) -> None:
        on = self.on
        d = targets - self.pos
        dist = np.linalg.norm(d, axis=1, keepdims=True)
        speed = np.minimum(caps[:, None], 1.6 * dist)
        desired = np.where(dist > 1e-6, d / np.maximum(dist, 1e-6), 0.0) * speed
        dv = desired - self.vel
        dvn = np.linalg.norm(dv, axis=1, keepdims=True)
        lim = (self.acc * self.fm.accel_mod())[:, None] * DT * 1.6
        dv = np.where(dvn > lim, dv / np.maximum(dvn, 1e-9) * lim, dv)
        self.vel[on] += dv[on]
        self.pos[on] += self.vel[on] * DT
        self.pos[on] = np.clip(self.pos[on], [-2.0, -2.0], [L + 2.0, W + 2.0])

    def _update_fatigue(self) -> None:
        self.fm.step(np.linalg.norm(self.vel, axis=1), DT, self.on.astype(float))

    # ------------------------------------------------------------------ ball
    def _update_ball(self) -> None:
        if self.mode == OWNED:
            o = self.owner
            v = self.vel[o]
            sp = float(np.linalg.norm(v))
            fwd = v / sp if sp > 0.3 else np.array([1.0 if self.team[o] == HOME else -1.0, 0.0])
            self.ball[:2] = self.pos[o] + fwd * 0.45
            self.ball[2] = BALL_R
            self.ball_v = v.copy()
        elif self.mode == FLIGHT and self.flight:
            xy, z, done = self.flight.at(self.t)
            prev = self.ball[:2].copy()
            self.ball[:2], self.ball[2] = xy, z
            self.ball_v = (xy - prev) / DT
            if done:
                fl = self.flight
                self.flight = None
                self.mode = LOOSE
                self.loose_since = self.t
                self.loose_claim = None
                self.loose_intercept = False
                self.ball_v *= 0.25
                fl.on_arrive()
        elif self.mode == LOOSE:
            self.ball[:2] += self.ball_v * DT
            self.ball_v *= max(0.0, 1.0 - 1.4 * DT)
            self.ball[2] = BALL_R + (self.ball[2] - BALL_R) * 0.6
            self._loose_ball()
        elif self.mode == DEAD and self.restart:
            r = self.restart
            d = r.spot - self.ball[:2]
            n = float(np.linalg.norm(d))
            self.ball[:2] += d / n * min(n, 10.0 * DT) if n > 1e-6 else 0.0
            self.ball[2] = BALL_R
            self.ball_v[:] = 0
            if (
                self.t >= r.ready_at
                and n < 0.5
                and np.linalg.norm(self.pos[r.actor] - r.spot) < 1.5
            ):
                self._gain(r.actor, quiet=True)
                self.hold_until = self.t + 0.6
        self.ball[:2] = np.clip(self.ball[:2], [-4.5, -4.5], [L + 4.5, W + 4.5])

    def _loose_ball(self) -> None:
        x, y = self.ball[:2]
        if not (0.0 <= x <= L and 0.0 <= y <= W):
            self._out_of_play()
            return
        mask = self.on if self.loose_claim is None else self.on & (self.team == self.loose_claim)
        idx = np.flatnonzero(mask)
        d = np.linalg.norm(self.pos[idx] - self.ball[:2], axis=1)
        k = int(np.argmin(d))
        if d[k] < 1.0 or self.t - self.loose_since > 6.0:
            self._collect(int(idx[k]))

    def _collect(self, i: int) -> None:
        if self.loose_intercept:
            self.emit(
                EventType.INTERCEPTION,
                team_id=int(self.team[i]),
                player_id=i,
                start=self.ball[:2].copy(),
                outcome=Outcome.SUCCESS,
            )
        self._gain(i)

    def _out_of_play(self) -> None:
        team = 1 - self.last_touch_team if self.loose_claim is None else self.loose_claim
        x, y = self.ball[:2]
        spot = np.array([np.clip(x, 0.5, L - 0.5), np.clip(y, 0.3, W - 0.3)])
        own_goal_x = 0.0 if team == HOME else L
        if (x < 0 or x > L) and abs(spot[0] - own_goal_x) < 1.0:  # goal kick
            actor = self.gk_of(team)
            spot = rel(team, np.array([5.5, 34.0]))
        else:
            actor, _ = self.nearest(self.on_team(team, outfield=True), spot)
        self.begin_dead(team, spot, actor, 3.0)

    def kick(
        self,
        kind: str,
        kicker: int,
        end: np.ndarray,
        *,
        speed_avg: float,
        peak: float,
        z_end: float,
        on_arrive: Callable[[], None],
        roles: list[tuple[int, np.ndarray]],
        k: float | None = None,
    ) -> Flight:
        start = self.ball[:2].copy()
        d = float(np.linalg.norm(end - start))
        fl = Flight(
            kind=kind,
            start=start,
            end=end.copy(),
            t0=self.t,
            T=max(0.3, d / speed_avg),
            peak=peak,
            z_end=z_end,
            k=k if k is not None else (0.25 if peak > 1.0 else 0.35),
            on_arrive=on_arrive,
        )
        self.flight = fl
        self.flight_roles = roles
        self.mode = FLIGHT
        self.owner = -1
        self.last_touch_team = int(self.team[kicker])
        return fl

    # ------------------------------------------------------------------ decisions
    def _decide(self) -> None:
        o = self.owner
        team = int(self.team[o])
        fx, fy = rel(team, self.pos[o])
        pressure = self.pressure_on(o)
        u = self.rng.random(4)
        if not self.is_gk[o]:
            dist, angle = P.goal_geometry(fx, fy)
            if dist < 26.0:
                xg = P.xg(dist, angle, pressure, False, self.profiles[o].skill.finishing)
                eager = 1.6 if self.spell_team() == team else 1.0
                if dist < 26.0 and u[0] < min(0.8, eager * (0.03 + 1.3 * xg)):
                    self._shoot(o, pressure)
                    return
            if fx > 76.0 and abs(fy - 34.0) > 15.0 and u[1] < 0.22:
                self._cross(o, pressure)
                return
            if fx < 20.0 and pressure > 0.5 and u[2] < 0.6:
                self._clear(o)
                return
        self._choose_pass(o, team, pressure, u[3])

    def _choose_pass(self, o: int, team: int, pressure: float, u: float) -> None:
        mates = self.on_team(team)
        mates = mates[mates != o]
        opps = self.on_team(1 - team)
        start = self.pos[o]
        recv = np.clip(self.pos[mates] + self.vel[mates] * 0.6, [1, 1], [L - 1, W - 1])
        dists = np.linalg.norm(recv - start, axis=1)
        progress = np.array([rel(team, r)[0] for r in recv]) - rel(team, start)[0]
        defenders = self.kin(opps)
        evals = [
            P.pass_success(
                start, r, self.kin([m]), defenders, passing=self.passing[o], pressure=pressure
            )
            for m, r in zip(mates, recv, strict=True)
        ]
        p = np.array([e.p for e in evals])
        utility = p * (1.0 + 0.025 * np.clip(progress, -15, 40)) - (1 - p) * 1.6
        utility[self.is_gk[mates] & (pressure < 0.6)] -= 0.6
        utility[dists < 4.0] -= 0.5
        if utility.max() < 0.45 and pressure < 0.35 and not self.is_gk[o]:
            self.hold_until = self.t + 0.7  # nothing on: keep carrying
            return
        w = np.exp((utility - utility.max()) * 8.0)
        k = int(np.searchsorted(np.cumsum(w) / w.sum(), u))
        k = min(k, len(mates) - 1)
        m = int(mates[k])
        success = bool(self.rng.random() < p[k])
        ev = evals[k]
        self._pass(
            o,
            m,
            success,
            end=recv[k],
            interceptor=int(opps[ev.interceptor]) if ev.interceptor >= 0 else None,
            intercept_frac=ev.intercept_frac,
            pressure=pressure,
        )

    def _pass(
        self,
        o: int,
        m: int,
        success: bool,
        *,
        end: np.ndarray | None = None,
        interceptor: int | None = None,
        intercept_frac: float | None = None,
        lofted: bool | None = None,
        pressure: float | None = None,
        tags: tuple[str, ...] = (),
    ) -> None:
        team = int(self.team[o])
        start = self.ball[:2].copy()
        recv_pt = (
            end
            if end is not None
            else np.clip(self.pos[m] + self.vel[m] * 0.6, [1, 1], [L - 1, W - 1])
        )
        d = float(np.linalg.norm(recv_pt - start))
        lofted = d > LOFT_DISTANCE if lofted is None else lofted
        peak = min(10.0, 0.16 * d) if lofted else 0.0
        T, k = flight_params(d, lofted)
        speed_avg = max(d, 0.1) / T
        if pressure is None:
            pressure = self.pressure_on(o)
        if success:
            fl = self.kick(
                "pass",
                o,
                recv_pt,
                speed_avg=speed_avg,
                peak=peak,
                z_end=BALL_R,
                on_arrive=lambda: self._arrive(m),
                roles=[(m, recv_pt)],
                k=k,
            )
        else:
            opps = self.on_team(1 - team, outfield=True)
            lane_d, _ = _seg_dist(self.pos[opps], start, recv_pt)
            j = int(opps[np.argmin(lane_d)]) if interceptor is None else interceptor
            if intercept_frac is None:
                _, fj = _seg_dist(self.pos[j : j + 1], start, recv_pt)
                intercept_frac = float(fj[0])
            ip = start + (recv_pt - start) * float(np.clip(intercept_frac, 0.35, 0.95))
            fl = self.kick(
                "pass",
                o,
                ip,
                speed_avg=speed_avg,
                peak=peak * 0.6,
                z_end=BALL_R,
                on_arrive=lambda: self._arrive(j, intercept=True),
                roles=[(j, ip), (m, recv_pt)],
                k=k,
            )
        self.emit(
            EventType.PASS,
            team_id=team,
            player_id=o,
            start=start,
            end=recv_pt,
            target_id=m,
            outcome=Outcome.SUCCESS if success else Outcome.FAIL,
            ball_speed_ms=fl.v0,
            ball_height_m=max(BALL_R, fl.peak),
            pressure=pressure,
            tags=list(tags) + (["lofted"] if lofted else []),
        )

    def _arrive(self, i: int, intercept: bool = False) -> None:
        self.loose_claim = int(self.team[i])
        self.loose_intercept = intercept
        if np.linalg.norm(self.pos[i] - self.ball[:2]) < 2.5:
            self._collect(i)

    def _shoot(
        self,
        o: int,
        pressure: float,
        *,
        header: bool = False,
        goal: bool | None = None,
        miss: str | None = None,
        tags: tuple[str, ...] = (),
    ) -> None:
        team = int(self.team[o])
        fx, fy = rel(team, self.ball[:2])
        dist, angle = P.goal_geometry(fx, fy)
        xg = P.xg(dist, angle, pressure, header, self.profiles[o].skill.finishing)
        u = self.rng.random(3)
        scored = bool(u[0] < xg) if goal is None else goal
        gk = self.gk_of(1 - team)
        if scored:
            end_rel, result = np.array([106.0, 31.0 + 6.0 * u[1]]), "goal"
        else:
            result = miss or ("saved" if u[1] < 0.45 else "wide")
            if result == "saved":
                end_rel = rel(team, self.pos[gk]) + np.array([-0.5, 0.0])
            else:
                side = 1 if u[2] < 0.5 else -1
                end_rel = np.array([106.0, 34.0 + side * (4.6 + 4.0 * u[1])])
        end = rel(team, end_rel)
        fl = self.kick(
            "shot",
            o,
            end,
            speed_avg=13.0 if header else 24.0,
            peak=0.5 if header else 0.9,
            z_end=1.0 if header else 0.6,
            on_arrive=lambda: self._shot_arrive(o, result),
            roles=[(gk, end)] if result == "saved" else [],
        )
        self.emit(
            EventType.SHOT,
            team_id=team,
            player_id=o,
            start=fl.start,
            end=end,
            outcome=Outcome.SUCCESS if scored else Outcome.FAIL,
            ball_speed_ms=fl.v0,
            ball_height_m=fl.peak,
            pressure=pressure,
            tags=[result, *(["header"] if header else []), *tags],
        )

    def _shot_arrive(self, o: int, result: str) -> None:
        team = int(self.team[o])
        other = 1 - team
        if result == "goal":
            self.score[team] += 1
            self.emit(EventType.GOAL, team_id=team, player_id=o, start=self.ball[:2].copy())
            self.begin_dead(other, np.array([L / 2, W / 2]), self._kicker(other), 7.0, True)
        elif result == "saved":
            self._gain(self.gk_of(other))
        else:
            self.last_touch_team = team
            self._out_of_play()

    def _cross(self, o: int, pressure: float, *, landing: np.ndarray | None = None) -> None:
        team = int(self.team[o])
        _, fy = rel(team, self.ball[:2])
        u = self.rng.random(3)
        if landing is None:
            far = 40.0 if fy < 34.0 else 28.0
            landing = rel(team, np.array([93.0 + 5.0 * u[0], far + (u[1] - 0.5) * 10.0]))
        mates = self.on_team(team, outfield=True)
        att, _ = self.nearest(mates[mates != o], landing)
        dfd, _ = self.nearest(self.on_team(1 - team, outfield=True), landing)
        t_ball = float(np.linalg.norm(landing - self.ball[:2])) / 17.0
        p_att = P.aerial_win(
            self.kin([att]),
            self.reach(att),
            self.aerial[att],
            self.kin([dfd]),
            self.reach(dfd),
            self.aerial[dfd],
            landing,
            2.4,
            t_ball,
        )
        att_wins = bool(u[2] < p_att)
        self._delivery(o, att, dfd, landing, att_wins, pressure, ())

    def _delivery(
        self,
        o: int,
        att: int,
        dfd: int,
        landing: np.ndarray,
        att_wins: bool,
        pressure: float,
        tags: tuple[str, ...],
        duel_tags: tuple[str, ...] = (),
        header_goal: bool | None = None,
    ) -> None:
        team = int(self.team[o])

        def arrive() -> None:
            self.emit(
                EventType.AERIAL_DUEL,
                team_id=1 - team,
                player_id=dfd,
                target_id=att,
                start=self.ball[:2].copy(),
                outcome=Outcome.FAIL if att_wins else Outcome.SUCCESS,
                ball_height_m=float(self.ball[2]),
                tags=list(duel_tags),
            )
            if att_wins and (header_goal is not None or self.rng.random() < 0.5):
                self._shoot(att, self.pressure_on(att), header=True, goal=header_goal, tags=tags)
            elif att_wins:  # knock-down: the ball drops loose in the box
                self.ball_v = self.rng.normal(0.0, 2.0, 2)
            else:
                self._clear(dfd, header=True)

        fl = self.kick(
            "cross",
            o,
            landing,
            speed_avg=17.0,
            peak=4.5,
            z_end=2.4,
            on_arrive=arrive,
            roles=[(att, landing), (dfd, landing)],
        )
        self.emit(
            EventType.CROSS,
            team_id=team,
            player_id=o,
            start=fl.start,
            end=landing,
            target_id=att,
            outcome=Outcome.SUCCESS if att_wins else Outcome.FAIL,
            ball_speed_ms=fl.v0,
            ball_height_m=fl.peak,
            pressure=pressure,
            tags=list(tags),
        )

    def _clear(self, o: int, header: bool = False) -> None:
        team = int(self.team[o])
        u = self.rng.random(2)
        end = rel(team, np.array([48.0 + 20.0 * u[0], 8.0 + 52.0 * u[1]]))
        self.ball[2] = max(self.ball[2], BALL_R)
        fl = self.kick(
            "clearance",
            o,
            end,
            speed_avg=16.0 if header else 20.0,
            peak=6.0 if header else 12.0,
            z_end=BALL_R,
            on_arrive=lambda: None,
            roles=[],
        )
        self.emit(
            EventType.CLEARANCE,
            team_id=team,
            player_id=o,
            start=fl.start,
            end=end,
            ball_speed_ms=fl.v0,
            ball_height_m=fl.peak,
            tags=["header"] if header else [],
        )

    # ------------------------------------------------------------------ contact
    def _duels(self) -> None:
        o = self.owner
        team = int(self.team[o])
        idx = self.on_team(1 - team, outfield=True)
        idx = idx[self.press_block[idx] <= self.t]
        if len(idx) == 0:
            return
        j, d = self.nearest(idx, self.pos[o])
        u = self.rng.random(4)
        hazard = DUEL_HAZARD * (2.0 if self.spell_team() >= 0 else 1.0)
        if d > 1.5 or u[3] > hazard * DT:  # a challenge happens at a steady rate in contact
            return
        start = self.pos[o].copy()
        if self.profiles[o].archetype in DRIBBLERS and u[0] < 0.6:
            legs = float(self.fm.accel_mod()[o] / self.fm.accel_mod()[j])
            ok = bool(u[1] < P.duel_success(self.carry_skill[o], self.tackle[j], legs))
            self.emit(
                EventType.DRIBBLE,
                team_id=team,
                player_id=o,
                target_id=j,
                start=start,
                outcome=Outcome.SUCCESS if ok else Outcome.FAIL,
            )
            if ok:
                self.press_block[j] = self.t + 2.5
                self.hold_until = min(self.hold_until, self.t + 0.6)
                return
            self.emit(
                EventType.TACKLE,
                team_id=1 - team,
                player_id=j,
                target_id=o,
                start=start,
                outcome=Outcome.SUCCESS,
            )
            self._gain(j)
            return
        legs = float(self.fm.accel_mod()[j] / self.fm.accel_mod()[o])
        ok = bool(u[1] < P.duel_success(self.tackle[j], self.carry_skill[o], legs))
        if not ok and u[2] < 0.22:
            self.emit(EventType.FOUL, team_id=1 - team, player_id=j, target_id=o, start=start)
            self.press_block[j] = self.t + 4.0
            self.begin_dead(team, start, o, 4.0)
            return
        self.emit(
            EventType.TACKLE,
            team_id=1 - team,
            player_id=j,
            target_id=o,
            start=start,
            outcome=Outcome.SUCCESS if ok else Outcome.FAIL,
        )
        if ok:
            self._gain(j)
        else:
            self.press_block[j] = self.t + 2.0

    def _pressure_events(self) -> None:
        if self.mode != OWNED:
            return
        o = self.owner
        j, d = self.nearest(self.on_team(1 - int(self.team[o]), outfield=True), self.pos[o])
        if d < 2.5 and self.t - self.last_pressure.get(o, -99.0) > 5.0:
            self.last_pressure[o] = self.t
            self.emit(
                EventType.PRESSURE,
                team_id=int(self.team[j]),
                player_id=j,
                target_id=o,
                start=self.pos[j].copy(),
                pressure=P.pressure_from_distance(d),
            )

    # ------------------------------------------------------------------ squad changes
    def _substitutions(self) -> None:
        while self.knocks and self.t >= self.knocks[0][0]:
            _, i = self.knocks.pop(0)
            self.fm.knocked[i] = True
            self.emit(
                EventType.KNOCK,
                team_id=int(self.team[i]),
                player_id=i,
                start=self.pos[i].copy(),
            )
        if not self.subs or self.scripted:
            return
        t_due, out, inn = self.subs[0]
        if self.t < t_due or out == self.owner:
            return
        if self.mode != DEAD and self.t < t_due + 90.0:
            return
        self.subs.pop(0)
        self.on[out] = False
        self.on[inn] = True
        self.base[inn] = self.base[out]
        self.pos[inn] = [L / 2 + (2.0 if self.team[inn] == AWAY else -2.0), -1.0]
        self.shape[inn] = self.pos[inn]
        self.vel[inn] = 0
        self.vel[out] = 0
        self.emit(
            EventType.SUBSTITUTION,
            team_id=int(self.team[inn]),
            player_id=inn,
            target_id=out,
            start=self.pos[inn].copy(),
        )
