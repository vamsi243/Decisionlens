"""What-if: swap the actor for another profile and recompute the moment's probability.

Three kinds of swap:
* archetype  - a textbook player of an archetype, carrying the actor's current fatigue;
* substitute - a real bench player with fresh legs (fatigue 0);
* custom     - the actor's own profile with some attributes changed.

Both scenarios use the same Monte Carlo seed (common random numbers), so the before/after
difference reflects the swap, not sampling noise. `drivers` list the attribute differences that
matter for this kind of moment, in plain words ("+12 cm reach", "0.15 s faster reaction").
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from contracts import (
    Archetype,
    Driver,
    Modifiers,
    MomentType,
    PlayerProfile,
    Point,
    ProfileKind,
    ProfileRef,
    Scenario,
    WhatIf,
)
from engine.moments import PASS_MOMENTS, MomentSpec, danger_point, evaluate
from engine.montecarlo import RUNS, prob_range, seed_for
from engine.profiles import ARCHETYPE_LABEL, archetype_profile, effective_reach_cm
from engine.snapshot import Snapshot

FACTORS: dict[MomentType, tuple[str, ...]] = {
    MomentType.AERIAL_DUEL: ("reach", "aerial", "reaction", "fatigue"),
    MomentType.RECOVERY_RUN: ("speed", "accel", "reaction", "fatigue"),
    MomentType.BIG_CHANCE: ("finishing", "fatigue"),
    MomentType.LINE_BREAKING_PASS: ("passing",),
    MomentType.PRESS_TURNOVER: ("passing", "reaction"),
}
PREFERRED_ARCHETYPE = {
    MomentType.AERIAL_DUEL: Archetype.AERIAL_CB,
    MomentType.RECOVERY_RUN: Archetype.OVERLAPPING_FB,
    MomentType.BIG_CHANCE: Archetype.TARGET_MAN,
    MomentType.LINE_BREAKING_PASS: Archetype.DEEP_PLAYMAKER,
    MomentType.PRESS_TURNOVER: Archetype.BALL_PLAYING_CB,
}


def fatigue_of(mod: Modifiers) -> float:
    """Invert the reaction modifier (knocks don't touch it) back to a 0-100 fatigue score."""
    return round((mod.reaction - 1.0) / 0.004, 1)


def _attrs(p: PlayerProfile, m: Modifiers) -> dict[str, float]:
    return {
        "reach": effective_reach_cm(p, m),
        "speed": p.physical.max_speed_ms * m.speed,
        "accel": p.physical.accel_ms2 * m.accel,
        "reaction": p.physical.reaction_s * m.reaction,
        "aerial": p.skill.aerial,
        "passing": p.skill.passing,
        "finishing": p.skill.finishing,
        "fatigue": fatigue_of(m),
    }


def _driver(factor: str, a: float, b: float) -> Driver | None:
    d = b - a
    if factor == "reach" and abs(d) >= 2:
        return Driver(factor="jump_reach", delta=round(d, 1), unit="cm", text=f"{d:+.0f} cm reach")
    if factor == "speed" and abs(d) >= 0.1:
        return Driver(
            factor="top_speed", delta=round(d, 2), unit="m/s", text=f"{d:+.1f} m/s top speed"
        )
    if factor == "accel" and abs(d) >= 0.1:
        return Driver(
            factor="acceleration",
            delta=round(d, 2),
            unit="m/s2",
            text=f"{d:+.1f} m/s² acceleration",
        )
    if factor == "reaction" and abs(d) >= 0.01:
        word = "faster" if d < 0 else "slower"
        return Driver(
            factor="reaction", delta=round(d, 3), unit="s", text=f"{abs(d):.2f} s {word} reaction"
        )
    if factor in ("aerial", "passing", "finishing") and abs(d) >= 2:
        return Driver(factor=factor, delta=round(d, 1), unit="rating", text=f"{d:+.0f} {factor}")
    if factor == "fatigue" and abs(d) >= 5:
        text = (
            f"fresher legs (fatigue {a:.0f} → {b:.0f})"
            if d < 0
            else f"tired legs ({a:.0f} → {b:.0f})"
        )
        return Driver(factor="fatigue", delta=round(d, 1), unit="points", text=text)
    return None


def drivers(
    kind: MomentType, actual: tuple[PlayerProfile, Modifiers], swap: tuple[PlayerProfile, Modifiers]
) -> list[Driver]:
    a, b = _attrs(*actual), _attrs(*swap)
    found = [_driver(f, a[f], b[f]) for f in FACTORS[kind]]
    return [d for d in found if d is not None]


# --- building swaps ---------------------------------------------------------------------------


def _article(noun: str) -> str:
    return "An" if noun[:1].lower() in "aeiou" else "A"


def swap_archetype(
    snap: Snapshot, actor_id: str, archetype: Archetype
) -> tuple[ProfileRef, PlayerProfile, Modifiers]:
    prof = archetype_profile(archetype, actor_id, snap.team_of(actor_id))
    ref = ProfileRef(
        kind=ProfileKind.ARCHETYPE,
        archetype=archetype,
        label=f"{_article(ARCHETYPE_LABEL[archetype])} {ARCHETYPE_LABEL[archetype]}",
    )
    return ref, prof, snap.modifiers[actor_id]


def swap_substitute(
    snap: Snapshot, actor_id: str, bench_id: str
) -> tuple[ProfileRef, PlayerProfile, Modifiers]:
    bench = snap.profiles[bench_id]
    prof = bench.model_copy(update={"player_id": actor_id})
    ref = ProfileRef(
        kind=ProfileKind.SUBSTITUTE, player_id=bench_id, label=f"{bench.name} (fresh sub)"
    )
    return ref, prof, Modifiers()


def swap_custom(
    snap: Snapshot, actor_id: str, physical: dict[str, float], skill: dict[str, float]
) -> tuple[ProfileRef, PlayerProfile, Modifiers]:
    base = snap.profiles[actor_id]
    prof = base.model_copy(
        update={
            "physical": base.physical.model_copy(update=physical),
            "skill": base.skill.model_copy(update=skill),
        }
    )
    PlayerProfile.model_validate(prof.model_dump())  # bounds check the custom values
    ref = ProfileRef(kind=ProfileKind.CUSTOM, player_id=actor_id, label="Custom profile")
    return ref, prof, snap.modifiers[actor_id]


def default_swap(
    snap: Snapshot, spec: MomentSpec, bench_ids: Sequence[str]
) -> tuple[ProfileRef, PlayerProfile, Modifiers]:
    """Prefer a fresh bench player of the right archetype; otherwise a textbook archetype."""
    want = PREFERRED_ARCHETYPE[spec.kind]
    team = snap.team_of(spec.actor_id)
    for bid in bench_ids:
        p = snap.profiles[bid]
        if p.team_id == team and p.archetype == want:
            return swap_substitute(snap, spec.actor_id, bid)
    return swap_archetype(snap, spec.actor_id, want)


# --- the what-if itself -----------------------------------------------------------------------


def _ghost(snap: Snapshot, spec: MomentSpec) -> list[Point]:
    start = snap.pos[snap.idx(spec.actor_id)]
    if spec.kind == MomentType.RECOVERY_RUN and spec.opponent_id:
        end: Any = spec.point or danger_point(snap, spec.opponent_id)
    elif spec.kind == MomentType.BIG_CHANCE:
        end = snap.rel(snap.team_of(spec.actor_id), [105.0, 34.0])
    else:
        end = spec.point or start
    return [Point(x=float(start[0]), y=float(start[1])), Point(x=float(end[0]), y=float(end[1]))]


def what_if(
    snap: Snapshot,
    spec: MomentSpec,
    moment_id: str,
    swap: tuple[ProfileRef, PlayerProfile, Modifiers],
    runs: int = RUNS,
) -> WhatIf:
    ref, prof, mod = swap
    actor = spec.actor_id
    actual = (snap.profiles[actor], snap.modifiers[actor])
    replace = {actor: (prof, mod)}
    seed = seed_for(moment_id, actor)
    p_before = evaluate(snap, spec)
    p_after = evaluate(snap, spec, replace)
    actual_ref = ProfileRef(
        kind=ProfileKind.ACTUAL,
        player_id=actor,
        label=f"{actual[0].name} (fatigue {fatigue_of(actual[1]):.0f})",
    )
    return WhatIf(
        moment_id=moment_id,
        actor_id=actor,
        actual=Scenario(
            profile=actual_ref,
            p_success=round(p_before, 4),
            range=prob_range(lambda r: evaluate(snap, spec, rng=r), seed, runs),
        ),
        counterfactual=Scenario(
            profile=ref,
            p_success=round(p_after, 4),
            range=prob_range(lambda r: evaluate(snap, spec, replace, rng=r), seed, runs),
        ),
        drivers=drivers(spec.kind, actual, (prof, mod)),
        ghost_path=_ghost(snap, spec) if spec.kind not in PASS_MOMENTS else [],
    )
