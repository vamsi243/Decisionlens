"""Engine payloads handed to the agents (and used for the grounding check and template cards).

Probabilities are given as whole percentages so the agents can quote them as written.
"""

from __future__ import annotations

from typing import Any

from contracts import KeyMoment, MomentType, WorkloadState
from contracts.stream import MomentAnalysis
from mcp_server.context import EngineContext

ACTION_WORD = {
    "pass": "pass",
    "cross": "cross",
    "shot": "shot",
    "carry": "carry forward",
    "dribble": "dribble",
    "clear": "clearance",
    "header": "header",
    "recovery_run": "recovery run",
}


def pct(p: float) -> int:
    return round(p * 100)


def minute(t_ms: int) -> int:
    return t_ms // 60_000 + 1


def moment_facts(ctx: EngineContext, a: MomentAnalysis) -> dict[str, Any]:
    m: KeyMoment = a.moment
    facts: dict[str, Any] = {
        "moment_id": m.moment_id,
        "minute": minute(m.t_ms),
        "type": m.type.value,
        "headline": m.title,
        "team": ctx.teams.get(m.team_id or "", ""),
        "players": [ctx.name(p) for p in m.players],
    }
    w = a.what_if
    if w is not None:
        facts["what_if"] = {
            "player": ctx.name(w.actor_id),
            "actual_pct": pct(w.actual.p_success),
            "actual_range_pct": [pct(w.actual.range.low), pct(w.actual.range.high)],
            "swap": w.counterfactual.profile.label,
            "swap_pct": pct(w.counterfactual.p_success),
            "swap_range_pct": [pct(w.counterfactual.range.low), pct(w.counterfactual.range.high)],
            "drivers": [d.text for d in w.drivers],
        }
    o = a.options
    if o is not None and o.options:
        opts = []
        for op in o.options:
            opts.append(
                {
                    "action": ACTION_WORD.get(op.action.value, op.action.value),
                    "to": ctx.name(op.target_id) if op.target_id else None,
                    "success_pct": pct(op.p_success),
                    "threat_gain": round(op.xt_gain, 3),
                    "best": op.option_id == o.best_option_id,
                    "chosen": op.chosen,
                }
            )
        facts["options"] = {"player": ctx.name(o.actor_id), "list": opts}
    wl: WorkloadState | None = ctx.workload_at(m.moment_id, m.players[0]) if m.players else None
    if wl is not None:
        facts["workload"] = {
            "player": ctx.name(wl.player_id),
            "fatigue": round(wl.fatigue),
            "distance_km": round(wl.distance_m / 1000, 1),
            "status": wl.status.value,
            "top_speed_loss_pct": round((1 - wl.modifiers.speed) * 100),
        }
    if m.type == MomentType.FATIGUE_ALERT and m.players:
        tired = ctx.players[m.players[0]]
        bench = [ctx.players[b["player_id"]] for b in ctx.bench(m.moment_id)]
        outfield = [b for b in bench if b.position.value != "GK"]
        same = [b for b in outfield if b.position == tired.position]
        facts["fresh_subs"] = [b.name for b in (same or outfield)][:2]
    return facts
