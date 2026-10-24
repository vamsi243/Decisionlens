"""One frame of match state, the input to every evaluator, option generator and what-if."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from contracts import Modifiers, PlayerProfile
from engine.physics import Kinematics
from engine.probability import pressure_from_distance
from engine.profiles import kinematics

Replacement = tuple[PlayerProfile, Modifiers]


@dataclass(frozen=True)
class Snapshot:
    frame: int
    t_ms: int
    home_team: str
    ids: list[str]  # players on the pitch
    teams: list[str]  # team id per player
    pos: np.ndarray  # (k, 2)
    vel: np.ndarray  # (k, 2)
    ball: np.ndarray  # (3,)
    owner_id: str | None
    profiles: Mapping[str, PlayerProfile]
    modifiers: Mapping[str, Modifiers]
    _index: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._index.update({pid: i for i, pid in enumerate(self.ids)})

    def idx(self, player_id: str) -> int:
        return self._index[player_id]

    def team_of(self, player_id: str) -> str:
        return self.profiles[player_id].team_id

    def team(self, team_id: str, outfield: bool = False) -> list[int]:
        return [
            i
            for i, (pid, t) in enumerate(zip(self.ids, self.teams, strict=True))
            if t == team_id and not (outfield and self.profiles[pid].position.value == "GK")
        ]

    def opponents(self, player_id: str, outfield: bool = False) -> list[int]:
        mine = self.team_of(player_id)
        other = next(t for t in set(self.teams) if t != mine)
        return self.team(other, outfield)

    def kin(self, idx: list[int], replace: Mapping[str, Replacement] | None = None) -> Kinematics:
        profiles, mods = [], []
        for i in idx:
            pid = self.ids[i]
            p, m = (replace or {}).get(pid, (self.profiles[pid], self.modifiers[pid]))
            profiles.append(p)
            mods.append(m)
        return kinematics(profiles, self.pos[idx], self.vel[idx], mods)

    def rel(self, team_id: str, xy: np.ndarray | list[float]) -> np.ndarray:
        """Absolute -> team-relative (attacking toward x = 105); an involution."""
        xy = np.asarray(xy, float)
        return xy if team_id == self.home_team else np.array([105.0, 68.0]) - xy

    def pressure_on(self, player_id: str) -> float:
        opp = self.opponents(player_id, outfield=True)
        if not opp:
            return 0.0
        d = np.linalg.norm(self.pos[opp] - self.pos[self.idx(player_id)], axis=1).min()
        return pressure_from_distance(float(d))
