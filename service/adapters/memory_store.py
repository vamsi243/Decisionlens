"""MemoryStore: process-local StateStore for RUN_MODE=local."""

from __future__ import annotations

from contracts import KeyMoment, MatchStats, Overlay
from contracts.stream import MomentAnalysis


class MemoryStore:
    def __init__(self) -> None:
        self._moments: dict[str, KeyMoment] = {}
        self._analyses: dict[str, MomentAnalysis] = {}
        self._overlays: dict[str, Overlay] = {}
        self._stats: MatchStats | None = None

    def put_moment(self, m: KeyMoment) -> None:
        self._moments[m.moment_id] = m

    def moments(self, until_ms: int | None = None) -> list[KeyMoment]:
        ms = sorted(self._moments.values(), key=lambda m: (m.t_ms, m.moment_id))
        return ms if until_ms is None else [m for m in ms if m.t_ms <= until_ms]

    def put_analysis(self, a: MomentAnalysis) -> None:
        self._analyses[a.moment.moment_id] = a

    def analysis(self, moment_id: str) -> MomentAnalysis | None:
        return self._analyses.get(moment_id)

    def put_overlay(self, o: Overlay) -> None:
        self._overlays[o.overlay_id] = o

    def overlay(self, overlay_id: str) -> Overlay | None:
        return self._overlays.get(overlay_id)

    def overlays(self, until_ms: int | None = None) -> list[Overlay]:
        os_ = sorted(self._overlays.values(), key=lambda o: (o.t_ms, o.overlay_id))
        return os_ if until_ms is None else [o for o in os_ if o.t_ms <= until_ms]

    def put_stats(self, s: MatchStats) -> None:
        self._stats = s

    def stats(self) -> MatchStats | None:
        return self._stats

    def reset_live(self) -> None:
        """After a seek the live stats are stale until the next frame; cached analyses stay."""
        self._stats = None
