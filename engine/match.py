"""Load a generated match into NumPy arrays and replay fatigue, for batch analysis."""

from __future__ import annotations

import gzip
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import orjson

from contracts import Event, EventType, MatchMeta, PlayerProfile, TrackingFrame
from engine.fatigue import FatigueModel, modifiers_for
from engine.snapshot import Snapshot


def iter_tracking(match_dir: Path) -> Iterator[bytes]:
    """Yield raw tracking lines from tracking.jsonl, falling back to tracking.jsonl.gz."""
    plain = match_dir / "tracking.jsonl"
    if plain.exists():
        with plain.open("rb") as f:
            yield from f
    else:
        with gzip.open(match_dir / "tracking.jsonl.gz", "rb") as f:
            yield from f


def read_jsonl(path: Path) -> list[bytes]:
    return [line for line in path.read_bytes().splitlines() if line.strip()]


@dataclass
class MatchData:
    dir: Path
    meta: MatchMeta
    players: list[PlayerProfile]
    events: list[Event]
    pos: np.ndarray  # (F, N, 2) float32, NaN when off the pitch
    vel: np.ndarray  # (F, N, 2) float32
    ball: np.ndarray  # (F, 3) float32
    owner: np.ndarray  # (F,) int16, -1 when nobody has the ball
    fatigue: np.ndarray  # (F, N) float32 replayed with the engine fatigue model
    knocked: np.ndarray  # (F, N) bool
    index: dict[str, int] = field(default_factory=dict)

    @property
    def ids(self) -> list[str]:
        return [p.player_id for p in self.players]

    @property
    def n_frames(self) -> int:
        return int(self.pos.shape[0])

    def profile(self, player_id: str) -> PlayerProfile:
        return self.players[self.index[player_id]]

    @classmethod
    def load(cls, match_dir: Path | str) -> MatchData:
        d = Path(match_dir)
        meta = MatchMeta.model_validate_json(read_jsonl(d / "meta.jsonl")[0])
        players = [PlayerProfile.model_validate_json(x) for x in read_jsonl(d / "players.jsonl")]
        events = [Event.model_validate_json(x) for x in read_jsonl(d / "events.jsonl")]
        index = {p.player_id: i for i, p in enumerate(players)}
        n = len(players)

        lines = list(iter_tracking(d))
        F = len(lines)
        pos = np.full((F, n, 2), np.nan, np.float32)
        vel = np.zeros((F, n, 2), np.float32)
        ball = np.zeros((F, 3), np.float32)
        owner = np.full(F, -1, np.int16)
        for f, line in enumerate(lines):
            fr = orjson.loads(line)
            b = fr["ball"]
            ball[f] = (b["x"], b["y"], b["z"])
            if b["owner_id"] is not None:
                owner[f] = index[b["owner_id"]]
            for p in fr["players"]:
                i = index[p["id"]]
                pos[f, i] = (p["x"], p["y"])
                vel[f, i] = (p["vx"], p["vy"])

        fatigue, knocked = cls._replay_fatigue(vel, ~np.isnan(pos[:, :, 0]), events, index)
        return cls(d, meta, players, events, pos, vel, ball, owner, fatigue, knocked, index)

    @staticmethod
    def _replay_fatigue(
        vel: np.ndarray, on: np.ndarray, events: list[Event], index: dict[str, int]
    ) -> tuple[np.ndarray, np.ndarray]:
        F, n = on.shape
        model = FatigueModel(n)
        knocks = sorted(
            (e.frame_ref, index[e.player_id])
            for e in events
            if e.type == EventType.KNOCK and e.player_id
        )
        out = np.zeros((F, n), np.float32)
        knocked = np.zeros((F, n), bool)
        speed = np.linalg.norm(vel, axis=2)
        k = 0
        for f in range(F):
            while k < len(knocks) and knocks[k][0] <= f:
                model.knocked[knocks[k][1]] = True
                k += 1
            model.step(speed[f], 0.1, on[f].astype(float))
            out[f] = model.fatigue
            knocked[f] = model.knocked
        return out, knocked

    def frame(self, f: int) -> TrackingFrame:
        """Rebuild one TrackingFrame record (handy for tests and tools)."""
        on = np.flatnonzero(~np.isnan(self.pos[f, :, 0]))
        o = int(self.owner[f])
        return TrackingFrame.model_validate(
            {
                "frame": f,
                "t_ms": f * 100,
                "period": "1H" if f * 100 < self.meta.period_length_ms else "2H",
                "ball": {
                    "x": float(self.ball[f, 0]),
                    "y": float(self.ball[f, 1]),
                    "z": float(self.ball[f, 2]),
                    "owner_id": self.players[o].player_id if o >= 0 else None,
                },
                "players": [
                    {
                        "id": self.players[i].player_id,
                        "x": float(self.pos[f, i, 0]),
                        "y": float(self.pos[f, i, 1]),
                        "vx": float(self.vel[f, i, 0]),
                        "vy": float(self.vel[f, i, 1]),
                    }
                    for i in on
                ],
            }
        )

    def snapshot(self, f: int) -> Snapshot:
        on = np.flatnonzero(~np.isnan(self.pos[f, :, 0]))
        ids = [self.players[i].player_id for i in on]
        o = int(self.owner[f])
        return Snapshot(
            frame=f,
            t_ms=f * 100,
            home_team=self.meta.teams[0].team_id,
            ids=ids,
            teams=[self.players[i].team_id for i in on],
            pos=self.pos[f, on].astype(float),
            vel=self.vel[f, on].astype(float),
            ball=self.ball[f].astype(float),
            owner_id=self.players[o].player_id if o >= 0 else None,
            profiles={p.player_id: p for p in self.players},
            modifiers={
                self.players[i].player_id: modifiers_for(
                    float(self.fatigue[f, i]), bool(self.knocked[f, i])
                )
                for i in range(len(self.players))
            },
        )

    def bench(self, f: int, team_id: str) -> list[str]:
        """Players of `team_id` who have not appeared by frame f (fresh substitutes)."""
        played = ~np.isnan(self.pos[: f + 1, :, 0]).all(axis=0)
        return [
            p.player_id
            for i, p in enumerate(self.players)
            if p.team_id == team_id and not played[i]
        ]

    def first_owned_after(self, f: int, player_id: str, within: int = 80) -> int:
        """First frame after f where `player_id` has the ball (or f if never within the window)."""
        i = self.index[player_id]
        hits = np.flatnonzero(self.owner[f : f + within] == i)
        return f + int(hits[0]) if len(hits) else f
