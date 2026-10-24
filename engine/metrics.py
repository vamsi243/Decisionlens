"""Incremental metrics: workload per player, team stats, intensity windows, heat maps.

Everything here is incremental (feed frames and events as they stream), so the live service and
batch analysis share one implementation.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from contracts import (
    Event,
    EventType,
    IntensityPoint,
    MatchMeta,
    MatchStats,
    Outcome,
    TeamStats,
    WorkloadState,
)
from engine.fatigue import FatigueModel
from engine.probability import goal_geometry, xg

HSR_SPEED = 5.5  # m/s (19.8 km/h)
SPRINT_SPEED = 7.0  # m/s (25.2 km/h)
SPRINT_MIN_S = 1.0
HEAT_NX, HEAT_NY = 21, 14  # 5 m cells
WINDOW_MS = 5 * 60 * 1000
DUEL_TYPES = {EventType.TACKLE, EventType.DRIBBLE, EventType.AERIAL_DUEL}


def shot_xg(e: Event, home_team: str, finishing: float = 70.0) -> float:
    """xG of a logged shot, from its position, pressure and whether it was a header."""
    if e.start is None:
        return 0.0
    x, y = e.start.x, e.start.y
    if e.team_id != home_team:
        x, y = 105.0 - x, 68.0 - y
    dist, angle = goal_geometry(x, y)
    return xg(dist, angle, e.pressure or 0.0, "header" in e.tags, finishing)


class WorkloadTracker:
    """Distance, high-speed running, sprints, heat map and fatigue for every squad player."""

    def __init__(self, player_ids: Sequence[str], hz: int = 10) -> None:
        self.ids = list(player_ids)
        self.index = {pid: i for i, pid in enumerate(self.ids)}
        n = len(self.ids)
        self.dt = 1.0 / hz
        self.distance = np.zeros(n)
        self.hsr = np.zeros(n)
        self.sprints = np.zeros(n, int)
        self._sprint_time = np.zeros(n)
        self._prev = np.full((n, 2), np.nan)
        self.heat = np.zeros((n, HEAT_NX, HEAT_NY))
        self.fatigue = FatigueModel(n)
        self.frames = 0
        self.hsr_total = 0.0  # all players, for intensity

    def knock(self, player_id: str) -> None:
        self.fatigue.knocked[self.index[player_id]] = True

    def update(self, ids: Sequence[str], pos: np.ndarray, vel: np.ndarray) -> None:
        idx = np.array([self.index[i] for i in ids])
        pos = np.asarray(pos, float)
        speed_on = np.linalg.norm(np.asarray(vel, float), axis=1)

        step = np.linalg.norm(pos - self._prev[idx], axis=1)
        step = np.where(np.isnan(step), 0.0, step)
        self.distance[idx] += step
        fast = speed_on > HSR_SPEED
        self.hsr[idx] += np.where(fast, step, 0.0)
        self.hsr_total += float(step[fast].sum())

        sprinting = speed_on > SPRINT_SPEED
        before = self._sprint_time[idx]
        after = np.where(sprinting, before + self.dt, 0.0)
        self.sprints[idx] += (before < SPRINT_MIN_S) & (after >= SPRINT_MIN_S)
        self._sprint_time[idx] = after

        self._prev[:] = np.nan
        self._prev[idx] = pos

        speed = np.zeros(len(self.ids))
        speed[idx] = speed_on
        active = np.zeros(len(self.ids))
        active[idx] = 1.0
        self.fatigue.step(speed, self.dt, active)

        if self.frames % 10 == 0:  # heat map sampled once a second
            cx = np.clip((pos[:, 0] / 105.0 * HEAT_NX).astype(int), 0, HEAT_NX - 1)
            cy = np.clip((pos[:, 1] / 68.0 * HEAT_NY).astype(int), 0, HEAT_NY - 1)
            np.add.at(self.heat, (idx, cx, cy), 1.0)
        self.frames += 1

    def state(self, player_id: str, t_ms: int) -> WorkloadState:
        i = self.index[player_id]
        return WorkloadState(
            t_ms=t_ms,
            player_id=player_id,
            distance_m=round(float(self.distance[i]), 1),
            hsr_m=round(float(self.hsr[i]), 1),
            sprints=int(self.sprints[i]),
            recent_load=round(float(self.fatigue.recent_load[i]), 3),
            fatigue=round(float(self.fatigue.fatigue[i]), 1),
            status=self.fatigue.status(i),
            modifiers=self.fatigue.modifiers(i),
        )

    def heatmap(self, player_id: str) -> np.ndarray:
        h = self.heat[self.index[player_id]]
        return np.asarray(h / max(1.0, float(h.sum())), dtype=float)


class StatsTracker:
    """Team stats recounted from events (plus possession from tracking ownership)."""

    def __init__(self, meta: MatchMeta, finishing: dict[str, float] | None = None) -> None:
        self.team_ids = [t.team_id for t in meta.teams]
        self.home = self.team_ids[0]
        self.finishing = finishing or {}
        self.owned = {t: 0 for t in self.team_ids}
        z: dict[str, float] = {t: 0.0 for t in self.team_ids}
        self.c = {
            k: dict(z)
            for k in (
                "passes",
                "completed",
                "pass_dist",
                "pass_speed",
                "shots",
                "on_target",
                "goals",
                "xg",
                "max_shot_speed",
                "tackles_won",
                "interceptions",
            )
        }

    def update_frame(self, owner_id: str | None) -> None:
        if owner_id:
            self.owned[owner_id[:3]] += 1

    def update_event(self, e: Event) -> None:
        t = e.team_id
        if t is None:
            return
        c = self.c
        if e.type == EventType.PASS:
            c["passes"][t] += 1
            c["completed"][t] += e.outcome == Outcome.SUCCESS
            if e.start and e.end:
                c["pass_dist"][t] += float(np.hypot(e.end.x - e.start.x, e.end.y - e.start.y))
            c["pass_speed"][t] += e.ball_speed_ms or 0.0
        elif e.type == EventType.SHOT:
            c["shots"][t] += 1
            c["on_target"][t] += bool({"goal", "saved"} & set(e.tags))
            c["max_shot_speed"][t] = max(c["max_shot_speed"][t], e.ball_speed_ms or 0.0)
            c["xg"][t] += self.shot_xg(e)
        elif e.type == EventType.GOAL:
            c["goals"][t] += 1
        elif e.type == EventType.TACKLE and e.outcome == Outcome.SUCCESS:
            c["tackles_won"][t] += 1
        elif e.type == EventType.INTERCEPTION:
            c["interceptions"][t] += 1

    def shot_xg(self, e: Event) -> float:
        return shot_xg(e, self.home, self.finishing.get(e.player_id or "", 70.0))

    def snapshot(self, t_ms: int, distance_km: dict[str, float] | None = None) -> MatchStats:
        total = max(1, sum(self.owned.values()))
        c = self.c
        teams = []
        for t in self.team_ids:
            n = int(c["passes"][t])
            teams.append(
                TeamStats(
                    team_id=t,
                    possession=round(self.owned[t] / total, 4) if sum(self.owned.values()) else 0.5,
                    passes=n,
                    passes_completed=int(c["completed"][t]),
                    pass_accuracy=round(c["completed"][t] / n, 4) if n else 0.0,
                    avg_pass_distance_m=round(c["pass_dist"][t] / n, 2) if n else 0.0,
                    avg_pass_speed_ms=round(c["pass_speed"][t] / n, 2) if n else 0.0,
                    shots=int(c["shots"][t]),
                    shots_on_target=int(c["on_target"][t]),
                    goals=int(c["goals"][t]),
                    xg=round(c["xg"][t], 3),
                    max_shot_speed_ms=round(c["max_shot_speed"][t], 2),
                    tackles_won=int(c["tackles_won"][t]),
                    interceptions=int(c["interceptions"][t]),
                    distance_km=round((distance_km or {}).get(t, 0.0), 2),
                )
            )
        return MatchStats(t_ms=t_ms, teams=teams)


class IntensityTracker:
    """Intensity index per 5-minute window: how hard and how dangerously the match is played.

    raw = 20 x (window HSR / average HSR of earlier windows)     (physical, fatigue-neutral)
        + 2.5 x duels + 0.3 x pressures + 1 x possession changes  (contest)
        + 40 x xG + 12 x goals + 6 x dangerous turnovers          (threat)
    index = min(100, 100 x raw / 125). A dangerous turnover is a possession change within 30 m
    of the losing team's goal. Normalising HSR by the match so far keeps late, tired windows
    comparable with early ones, and everything is computable live.
    """

    REF = 125.0
    FIRST_HSR = 2400.0  # baseline for the first window, before there is a history

    def __init__(self, meta: MatchMeta, finishing: dict[str, float] | None = None) -> None:
        self.home = meta.teams[0].team_id
        self.finishing = finishing or {}
        self.windows: dict[int, dict[str, float]] = {}

    def _w(self, t_ms: int) -> dict[str, float]:
        return self.windows.setdefault(
            t_ms // WINDOW_MS,
            dict.fromkeys(
                ("hsr", "duels", "shots", "pressures", "turnovers", "danger", "xg", "goals"), 0.0
            ),
        )

    def add_hsr(self, t_ms: int, metres: float) -> None:
        self._w(t_ms)["hsr"] += metres

    def update_event(self, e: Event) -> None:
        w = self._w(e.t_ms)
        if e.type in DUEL_TYPES:
            w["duels"] += 1
        elif e.type == EventType.SHOT:
            w["shots"] += 1
            w["xg"] += shot_xg(e, self.home, self.finishing.get(e.player_id or "", 70.0))
        elif e.type == EventType.GOAL:
            w["goals"] += 1
        elif e.type == EventType.PRESSURE:
            w["pressures"] += 1
        elif e.type == EventType.POSSESSION_CHANGE and e.start is not None:
            w["turnovers"] += 1
            # The new owner's team won it; the loser defends x = 0 if the winner is away.
            near_loser_goal = e.start.x > 75.0 if e.team_id == self.home else e.start.x < 30.0
            w["danger"] += near_loser_goal

    def series(self) -> list[IntensityPoint]:
        out = []
        history: list[float] = []
        for k in sorted(self.windows):
            w = self.windows[k]
            baseline = sum(history) / len(history) if history else self.FIRST_HSR
            raw = (
                20.0 * w["hsr"] / max(1.0, baseline)
                + 2.5 * w["duels"]
                + 0.3 * w["pressures"]
                + 1.0 * w["turnovers"]
                + 40.0 * w["xg"]
                + 12.0 * w["goals"]
                + 6.0 * w["danger"]
            )
            history.append(w["hsr"])
            out.append(
                IntensityPoint(
                    window_start_ms=k * WINDOW_MS,
                    window_end_ms=(k + 1) * WINDOW_MS,
                    index=round(min(100.0, 100.0 * raw / self.REF), 1),
                    hsr_m=round(w["hsr"], 1),
                    duels=int(w["duels"]),
                    shots=int(w["shots"]),
                    pressures=int(w["pressures"]),
                    xg=round(w["xg"], 3),
                    goals=int(w["goals"]),
                    dangerous_turnovers=int(w["danger"]),
                )
            )
        return out
