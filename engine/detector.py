"""Key-moment detector (F10): watches the live stream and flags moments worth explaining.

It never looks at the generator's `scripted` tags. Every rule uses only events, tracking and
engine numbers, so it works the same on any match:

- aerial_duel: a header is lost inside the defender's own penalty box.
- recovery_run: an attacker beats a defender in the final third after the defender sprinted
  back (> 6.5 m/s in the last 20 s).
- big_chance: a shot with xG >= 0.25 is missed.
- goal: a goal is scored (analysed as the shot that scored it).
- line_breaking_pass: a ground pass completes >= 20 m forward past >= 4 opponents within 15 m
  of the line of the pass.
- press_turnover: a pass is lost in the passer's own third with >= 2 opponents within 6 m.
- fatigue_alert: an on-pitch player's fatigue first crosses 80.

Moments involving the same player within 6 s are merged (first one wins). Moment ids are
deterministic (`km_<frame>_<type>`) so a replay after seeking finds the same moments.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from contracts import (
    Event,
    EventType,
    FrameRange,
    KeyMoment,
    MatchMeta,
    MomentType,
    Outcome,
    PlayerProfile,
    Position,
)
from engine.fatigue import modifiers_for
from engine.metrics import shot_xg
from engine.moments import MomentSpec, danger_point
from engine.snapshot import Snapshot

BUFFER_FRAMES = 200  # 20 s of history
MERGE_MS = 6000
FATIGUE_ALERT = 80.0
BIG_CHANCE_XG = 0.25
LINE_BREAK_PROGRESS_M = 20.0
LINE_BREAK_BYPASSED = 4
LINE_BREAK_CORRIDOR_M = 15.0
DEFENDERS = {Position.CB, Position.FB, Position.DM}


@dataclass
class Detected:
    moment: KeyMoment
    spec: MomentSpec | None = None  # the question the engine should answer
    snapshot: Snapshot | None = None  # the frame to answer it at
    chosen: Event | None = None  # the on-ball action actually taken (for the option map)
    options_actor: str | None = None  # who to build an option map for, if anyone


@dataclass
class _Frame:
    frame: int
    ids: list[str]
    pos: np.ndarray
    vel: np.ndarray
    ball: np.ndarray
    owner_id: str | None
    fatigue: np.ndarray  # (n_players,) engine fatigue, squad order
    knocked: np.ndarray


@dataclass
class MomentDetector:
    meta: MatchMeta
    players: Sequence[PlayerProfile]
    buffer: deque[_Frame] = field(default_factory=lambda: deque(maxlen=BUFFER_FRAMES))
    last_cross: Event | None = None
    last_shot: Event | None = None
    alerted: set[str] = field(default_factory=set)
    recent: list[tuple[int, set[str]]] = field(default_factory=list)  # (t_ms, players)
    moments: list[KeyMoment] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.profiles: Mapping[str, PlayerProfile] = {p.player_id: p for p in self.players}
        self.order = [p.player_id for p in self.players]
        self.home = self.meta.teams[0].team_id
        self.names = {p.player_id: p.name.split()[-1] for p in self.players}

    # ------------------------------------------------------------------ inputs
    def on_frame(
        self,
        frame: int,
        ids: list[str],
        pos: np.ndarray,
        vel: np.ndarray,
        ball: np.ndarray,
        owner_id: str | None,
        fatigue: np.ndarray,
        knocked: np.ndarray,
    ) -> list[Detected]:
        self.buffer.append(
            _Frame(frame, ids, pos, vel, ball, owner_id, fatigue.copy(), knocked.copy())
        )
        out = []
        for pid in ids:
            i = self.order.index(pid)
            if fatigue[i] >= FATIGUE_ALERT and pid not in self.alerted:
                self.alerted.add(pid)
                d = self._make(
                    MomentType.FATIGUE_ALERT,
                    frame,
                    [pid],
                    self.profiles[pid].team_id,
                    None,
                    0.4,
                    f"{self.names[pid]} is running on empty",
                    merge=False,
                )
                if d:
                    out.append(d)
        return out

    def on_event(self, e: Event) -> list[Detected]:
        handler = {
            EventType.CROSS: self._cross,
            EventType.AERIAL_DUEL: self._aerial,
            EventType.DRIBBLE: self._dribble,
            EventType.SHOT: self._shot,
            EventType.GOAL: self._goal,
            EventType.PASS: self._pass,
        }.get(e.type)
        if handler is None:
            return []
        d = handler(e)
        return [d] if d else []

    # ------------------------------------------------------------------ helpers
    def _rel(self, team: str | None, x: float, y: float) -> tuple[float, float]:
        return (x, y) if team == self.home else (105.0 - x, 68.0 - y)

    def _at(self, frame: int) -> _Frame | None:
        for f in reversed(self.buffer):
            if f.frame <= frame:
                return f
        return self.buffer[0] if self.buffer else None

    def snapshot(self, frame: int) -> Snapshot | None:
        f = self._at(frame)
        if f is None:
            return None
        return Snapshot(
            frame=f.frame,
            t_ms=f.frame * 100,
            home_team=self.home,
            ids=list(f.ids),
            teams=[self.profiles[p].team_id for p in f.ids],
            pos=f.pos.astype(float),
            vel=f.vel.astype(float),
            ball=f.ball.astype(float),
            owner_id=f.owner_id,
            profiles=self.profiles,
            modifiers={
                pid: modifiers_for(float(f.fatigue[i]), bool(f.knocked[i]))
                for i, pid in enumerate(self.order)
            },
        )

    def _make(
        self,
        kind: MomentType,
        frame: int,
        players: list[str],
        team: str | None,
        event: Event | None,
        importance: float,
        title: str,
        merge: bool = True,
    ) -> Detected | None:
        t_ms = frame * 100
        involved = set(players)
        if merge and any(t_ms - t < MERGE_MS and involved & p for t, p in self.recent):
            return None
        self.recent = [(t, p) for t, p in self.recent if t_ms - t < MERGE_MS] + [(t_ms, involved)]
        m = KeyMoment(
            moment_id=f"km_{frame:05d}_{kind.value}",
            t_ms=t_ms,
            type=kind,
            team_id=team,
            players=players,
            frame_range=FrameRange(start=max(0, frame - 50), end=frame + 30),
            event_id=event.event_id if event else None,
            importance=round(min(1.0, importance), 3),
            title=title,
        )
        self.moments.append(m)
        return Detected(m)

    # ------------------------------------------------------------------ rules
    def _cross(self, e: Event) -> None:
        self.last_cross = e

    def _aerial(self, e: Event) -> Detected | None:
        if e.outcome != Outcome.FAIL or not (e.start and e.player_id and e.target_id):
            return None
        x, y = self._rel(e.team_id, e.start.x, e.start.y)  # defender's own goal at x = 0
        if not (x < 16.5 and abs(y - 34.0) < 20.16):
            return None
        d = self._make(
            MomentType.AERIAL_DUEL,
            e.frame_ref,
            [e.player_id, e.target_id],
            e.team_id,
            e,
            0.85,
            f"{self.names[e.target_id]} beats {self.names[e.player_id]} in the air",
        )
        cross = self.last_cross
        if d and cross and 0 < e.t_ms - cross.t_ms < 5000:
            d.spec = MomentSpec(
                MomentType.AERIAL_DUEL,
                frame=cross.frame_ref,
                actor_id=e.player_id,
                opponent_id=e.target_id,
                point=(e.start.x, e.start.y),
                ball_height_m=e.ball_height_m or 2.4,
                t_ball=(e.t_ms - cross.t_ms) / 1000.0,
            )
            d.snapshot = self.snapshot(cross.frame_ref)
        return d

    def _dribble(self, e: Event) -> Detected | None:
        if e.outcome != Outcome.SUCCESS or not (e.start and e.player_id and e.target_id):
            return None
        chaser = self.profiles[e.target_id]
        x, _ = self._rel(e.team_id, e.start.x, e.start.y)
        if x < 70.0 or chaser.position not in DEFENDERS:
            return None
        # Did the chaser sprint back, and when did the carrier get the ball?
        top, got = 0.0, None
        for f in reversed(self.buffer):
            if e.target_id in f.ids:
                v = f.vel[f.ids.index(e.target_id)]
                top = max(top, float(np.hypot(v[0], v[1])))
            if f.owner_id == e.player_id:
                got = f.frame
            elif got is not None:
                break
        if top < 6.5:
            return None
        d = self._make(
            MomentType.RECOVERY_RUN,
            e.frame_ref,
            [e.target_id, e.player_id],
            chaser.team_id,
            e,
            0.75,
            f"{self.names[e.player_id]} outruns {self.names[e.target_id]}",
        )
        if d:
            frame = got if got is not None else e.frame_ref
            d.snapshot = self.snapshot(frame)
            if d.snapshot and e.target_id in d.snapshot.ids and e.player_id in d.snapshot.ids:
                d.spec = MomentSpec(
                    MomentType.RECOVERY_RUN,
                    frame=frame,
                    actor_id=e.target_id,
                    opponent_id=e.player_id,
                    point=danger_point(d.snapshot, e.player_id),
                )
        return d

    def _shot_spec(self, d: Detected, e: Event) -> None:
        assert e.player_id
        d.snapshot = self.snapshot(e.frame_ref)
        if d.snapshot and e.player_id in d.snapshot.ids:
            d.spec = MomentSpec(
                MomentType.BIG_CHANCE,
                frame=e.frame_ref,
                actor_id=e.player_id,
                header="header" in e.tags,
            )
            d.chosen, d.options_actor = e, e.player_id

    def _shot(self, e: Event) -> Detected | None:
        self.last_shot = e
        if not e.player_id or e.outcome == Outcome.SUCCESS:
            return None  # goals are handled by the goal event
        fin = self.profiles[e.player_id].skill.finishing
        xg = shot_xg(e, self.home, fin)
        if xg < BIG_CHANCE_XG:
            return None
        d = self._make(
            MomentType.BIG_CHANCE,
            e.frame_ref,
            [e.player_id],
            e.team_id,
            e,
            0.5 + xg,
            f"Big chance missed by {self.names[e.player_id]}",
        )
        if d:
            self._shot_spec(d, e)
        return d

    def _goal(self, e: Event) -> Detected | None:
        if not e.player_id:
            return None
        d = self._make(
            MomentType.GOAL,
            e.frame_ref,
            [e.player_id],
            e.team_id,
            e,
            1.0,
            f"Goal: {self.names[e.player_id]}",
            merge=False,
        )
        shot = self.last_shot
        if d and shot and shot.player_id == e.player_id and e.t_ms - shot.t_ms < 5000:
            self._shot_spec(d, shot)  # a goal is analysed as the shot that scored it
        return d

    def _pass(self, e: Event) -> Detected | None:
        if not (e.start and e.end and e.player_id and e.target_id):
            return None
        sx, _ = self._rel(e.team_id, e.start.x, e.start.y)
        ex, _ = self._rel(e.team_id, e.end.x, e.end.y)
        f = self._at(e.frame_ref)
        if f is None:
            return None
        opp = [
            i
            for i, pid in enumerate(f.ids)
            if self.profiles[pid].team_id != e.team_id
            and self.profiles[pid].position != Position.GK
        ]
        if e.outcome == Outcome.SUCCESS and "lofted" not in e.tags:
            if ex - sx < LINE_BREAK_PROGRESS_M:
                return None
            _, sy = self._rel(e.team_id, e.start.x, e.start.y)
            _, ey = self._rel(e.team_id, e.end.x, e.end.y)
            bypassed = 0
            for i in opp:  # opponents between passer and receiver, near the line of the pass
                ox, oy = self._rel(e.team_id, *f.pos[i])
                if sx < ox < ex:
                    lane_y = sy + (ey - sy) * (ox - sx) / (ex - sx)
                    bypassed += abs(oy - lane_y) < LINE_BREAK_CORRIDOR_M
            if bypassed < LINE_BREAK_BYPASSED:
                return None
            d = self._make(
                MomentType.LINE_BREAKING_PASS,
                e.frame_ref,
                [e.player_id, e.target_id],
                e.team_id,
                e,
                0.5 + 0.05 * bypassed,
                f"{self.names[e.player_id]} breaks the lines to {self.names[e.target_id]}",
            )
            kind = MomentType.LINE_BREAKING_PASS
        elif e.outcome == Outcome.FAIL and sx < 35.0:
            me = f.pos[f.ids.index(e.player_id)] if e.player_id in f.ids else None
            if me is None:
                return None
            close = sum(float(np.linalg.norm(f.pos[i] - me)) < 6.0 for i in opp)
            if close < 2:
                return None
            d = self._make(
                MomentType.PRESS_TURNOVER,
                e.frame_ref,
                [e.player_id],
                e.team_id,
                e,
                0.7,
                f"{self.names[e.player_id]} is pressed into a turnover",
            )
            kind = MomentType.PRESS_TURNOVER
        else:
            return None
        if d:
            d.snapshot = self.snapshot(e.frame_ref)
            d.spec = MomentSpec(
                kind,
                frame=e.frame_ref,
                actor_id=e.player_id,
                target_id=e.target_id,
                point=(e.end.x, e.end.y),
            )
            d.chosen, d.options_actor = e, e.player_id
        return d
