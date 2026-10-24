"""EngineContext: what the MCP tools can see, backed by the stream pipeline and state store.

Every answer is computed by the engine. Agents read numbers through these tools; they never make
them up. The same context serves the live service (tools mounted at /mcp) and the standalone
stdio server (`python -m mcp_server`), which replays a match file to full time first.
"""

from __future__ import annotations

from typing import Any, Literal

from contracts import Archetype, EventType, OptionSet, PlayerDecision, WhatIf, WorkloadState
from contracts.player import DecisionKind, DecisionOption
from contracts.stream import MomentAnalysis
from engine.whatif import (
    PREFERRED_ARCHETYPE,
    default_swap,
    swap_archetype,
    swap_custom,
    swap_substitute,
    what_if,
)
from service.pipeline import Pipeline
from service.ports import StateStore

SwapMode = Literal["fresh_sub", "archetype", "custom"]
PHYSICAL = ("height_cm", "max_speed_ms", "accel_ms2", "reaction_s", "jump_reach_cm")
SKILL = ("passing", "aerial", "tackle", "finishing")


def _minute(t_ms: int) -> int:
    return t_ms // 60_000 + 1


ACTION_WORD = {
    "pass": "pass",
    "cross": "cross",
    "shot": "shot",
    "carry": "carry forward",
    "dribble": "dribble",
}
LOST_WHAT = {
    EventType.TACKLE: "a tackle",
    EventType.AERIAL_DUEL: "an aerial duel",
    EventType.DRIBBLE: "a one-on-one",
}


def odds_pct(p: float) -> float:
    """Goal odds as a percentage: one decimal under 10%, whole numbers above."""
    v = p * 100
    return round(v, 1) if v < 10 else round(v)


def _swing(m: dict[str, Any]) -> tuple[float, float]:
    w = m.get("what_if")
    swing = abs(w["with_swap"] - w["actual"]) if w else 0.0
    return (swing if m["type"] != "goal" else swing / 2, m["importance"])


class EngineContext:
    def __init__(self, pipeline: Pipeline, store: StateStore) -> None:
        self.pipeline = pipeline
        self.store = store
        self.players = {p.player_id: p for p in pipeline.players}
        self.teams = {t.team_id: t.name for t in pipeline.meta.teams}
        self.swaps: dict[str, WhatIf] = {}  # moment id -> the swap an agent chose
        self.swap_log: list[dict[str, Any]] = []  # arguments of every swap, in order

    # ------------------------------------------------------------------ helpers
    def name(self, player_id: str | None) -> str:
        return self.players[player_id].name if player_id in self.players else "unknown"

    def _option(self, o: DecisionOption) -> dict[str, Any]:
        return {
            "action": ACTION_WORD.get(o.action.value, o.action.value),
            "to": self.name(o.target_id) if o.target_id else None,
            "goal_odds_pct": odds_pct(o.goal_odds),
        }

    def decision_facts(self, d: PlayerDecision) -> dict[str, Any]:
        """One ranked decision in words and engine numbers (template text and agent input)."""
        team_id = self.players[d.player_id].team_id
        opp_id = next(t for t in self.teams if t != team_id)
        f: dict[str, Any] = {
            "id": d.decision_id,
            "player": self.name(d.player_id),
            "team": self.teams[team_id],
            "opponents": self.teams[opp_id],
            "minute": _minute(d.t_ms),
            "kind": d.kind.value,
            "positive": d.positive,
            "followed": d.consequence.value,
            "window_s": 15,
        }
        if d.chosen is not None:
            f["chosen"] = self._option(d.chosen)
        if d.best is not None and d.goal_odds_gain > 0:
            f["better"] = self._option(d.best)
        if d.consequence_xg is not None:
            f["shot_xg_pct"] = odds_pct(d.consequence_xg)
        if d.kind == DecisionKind.DEFENDING:
            i = self.pipeline.event_index.get(d.decision_id.removeprefix("dec_"))
            e = self.pipeline.all_events[i] if i is not None else None
            if e is not None:
                beat = e.player_id if e.type == EventType.DRIBBLE else e.target_id
                f["lost"] = {"what": LOST_WHAT.get(e.type, "a duel"), "to": self.name(beat)}
        return f

    def _score(self) -> dict[str, int]:
        return {t.team_id: t.goals for t in self.pipeline.stats().teams}

    # ------------------------------------------------------------------ tools
    def match_state(self) -> dict[str, Any]:
        st = self.pipeline.state
        stats = self.pipeline.stats()
        t_ms = max(0, st.frame) * 100
        tired = sorted(self.pipeline.workload(), key=lambda w: -w.fatigue)[:3]
        return {
            "minute": _minute(t_ms),
            "t_ms": t_ms,
            "period": "second half"
            if t_ms >= self.pipeline.meta.period_length_ms
            else "first half",
            "score": {self.teams[t.team_id]: t.goals for t in stats.teams},
            "teams": [
                {
                    "team": self.teams[t.team_id],
                    "possession": t.possession,
                    "passes": t.passes,
                    "pass_accuracy": t.pass_accuracy,
                    "shots": t.shots,
                    "xg": t.xg,
                }
                for t in stats.teams
            ],
            "most_fatigued": [
                {"player": self.name(w.player_id), "fatigue": w.fatigue, "status": w.status.value}
                for w in tired
            ],
        }

    def workload(self, player_id: str) -> WorkloadState:
        if player_id not in self.players:
            raise ValueError(f"unknown player {player_id}")
        return self.pipeline.state.workload.state(
            player_id, max(0, self.pipeline.state.frame) * 100
        )

    def workload_at(self, moment_id: str, player_id: str) -> WorkloadState | None:
        """A player's workload when the moment happened (not now)."""
        return self.pipeline.moment_workload.get(moment_id, {}).get(player_id)

    def analysis(self, moment_id: str) -> MomentAnalysis | None:
        return self.store.analysis(moment_id)

    def options(self, moment_id: str) -> OptionSet | None:
        a = self.store.analysis(moment_id)
        return a.options if a else None

    def bench(self, moment_id: str) -> list[dict[str, str]]:
        return [
            {"player_id": b, "name": self.name(b), "archetype": self.players[b].archetype.value}
            for b in self.pipeline.moment_bench.get(moment_id, [])
        ]

    def what_if_swap(
        self,
        moment_id: str,
        mode: SwapMode,
        *,
        bench_player_id: str | None = None,
        archetype: str | None = None,
        overrides: dict[str, float] | None = None,
    ) -> WhatIf:
        d = self.pipeline.detected.get(moment_id)
        if d is None or d.spec is None or d.snapshot is None:
            raise ValueError(f"moment {moment_id} has no what-if (no engine question for it)")
        snap, spec = d.snapshot, d.spec
        bench = self.pipeline.moment_bench.get(moment_id, [])
        if mode == "fresh_sub":
            if bench_player_id is None:
                swap = default_swap(snap, spec, bench)
            elif bench_player_id not in bench:
                raise ValueError(f"{bench_player_id} is not a fresh substitute at this moment")
            else:
                swap = swap_substitute(snap, spec.actor_id, bench_player_id)
        elif mode == "archetype":
            arch = Archetype(archetype) if archetype else PREFERRED_ARCHETYPE[spec.kind]
            swap = swap_archetype(snap, spec.actor_id, arch)
        else:
            over = overrides or {}
            unknown = set(over) - set(PHYSICAL) - set(SKILL)
            if unknown:
                raise ValueError(f"unknown attributes: {sorted(unknown)}")
            swap = swap_custom(
                snap,
                spec.actor_id,
                {k: v for k, v in over.items() if k in PHYSICAL},
                {k: v for k, v in over.items() if k in SKILL},
            )
        w = what_if(snap, spec, moment_id, swap)
        self.swaps[moment_id] = w
        self.swap_log.append(
            {
                "mode": mode,
                "bench_player_id": bench_player_id,
                "archetype": archetype,
                "overrides": overrides,
            }
        )
        a = self.store.analysis(moment_id)
        if a is not None:
            self.store.put_analysis(a.model_copy(update={"what_if": w}))
        return w

    def intensity(self) -> list[dict[str, Any]]:
        return [p.model_dump(mode="json") for p in self.pipeline.state.intensity.series()]

    def recap_facts(self, until_ms: int | None = None) -> dict[str, Any]:
        st = self.pipeline.state
        t_ms = max(0, st.frame) * 100 if until_ms is None else until_ms
        stats = self.pipeline.stats()
        moments = []
        # Every moment the engine detected up to now, even ones a seek skipped past on screen.
        seen = {d.moment.moment_id: d.moment for d in self.pipeline.detected.values()}
        seen.update({m.moment_id: m for m in self.store.moments()})
        for m in sorted(seen.values(), key=lambda m: m.t_ms):
            if m.t_ms > t_ms or m.type.value == "fatigue_alert":
                continue
            a = self.store.analysis(m.moment_id)
            item: dict[str, Any] = {
                "moment_id": m.moment_id,
                "minute": _minute(m.t_ms),
                "type": m.type.value,
                "title": m.title,
                "importance": m.importance,
            }
            if a and a.what_if:
                item["what_if"] = {
                    "actual": a.what_if.actual.p_success,
                    "swap": a.what_if.counterfactual.profile.label,
                    "with_swap": a.what_if.counterfactual.p_success,
                    # as writers quote them
                    "actual_pct": round(a.what_if.actual.p_success * 100),
                    "with_swap_pct": round(a.what_if.counterfactual.p_success * 100),
                }
            moments.append(item)
        work = [st.workload.state(pid, t_ms) for pid in st.appeared]
        series = st.intensity.series()
        return {
            "minute": round(t_ms / 60_000),
            "score": {self.teams[t.team_id]: t.goals for t in stats.teams},
            "goals": [
                {
                    "minute": _minute(g.t_ms),
                    "team": self.teams.get(g.team_id or "", ""),
                    "scorer": self.name(g.player_id),
                }
                for g in st.goals
                if g.t_ms <= t_ms
            ],
            "teams": [
                {
                    "team": self.teams[t.team_id],
                    "possession": t.possession,
                    "pass_accuracy": t.pass_accuracy,
                    "shots": t.shots,
                    "xg": t.xg,
                }
                for t in stats.teams
            ],
            # biggest what-if swings first: those are the moments that could have gone either way
            "turning_points": sorted(moments, key=_swing, reverse=True)[:5],
            "furthest_running": [
                {"player": self.name(w.player_id), "km": round(w.distance_m / 1000, 1)}
                for w in sorted(work, key=lambda w: -w.distance_m)[:3]
            ],
            "most_fatigued": [
                {"player": self.name(w.player_id), "fatigue": w.fatigue}
                for w in sorted(work, key=lambda w: -w.fatigue)[:3]
            ],
            "most_intense_spells": [
                {"from_minute": p.window_start_ms // 60_000, "index": p.index}
                for p in sorted(series, key=lambda p: -p.index)[:2]
            ],
        }
