"""Write a simulated match to `{meta,players,events,tracking}.jsonl` (+ optional .gz)."""

from __future__ import annotations

import gzip
import shutil
from pathlib import Path

import numpy as np

from generator.roster import build_roster
from generator.script import install
from generator.sim import MatchSim


def _frame_line(sim: MatchSim) -> str:
    bx, by, bz = sim.ball
    owner = f'"{sim.ids[sim.owner]}"' if sim.owner >= 0 else "null"
    players = ",".join(
        f'{{"id":"{sim.ids[i]}","x":{sim.pos[i, 0]:.2f},"y":{sim.pos[i, 1]:.2f},'
        f'"vx":{sim.vel[i, 0]:.2f},"vy":{sim.vel[i, 1]:.2f}}}'
        for i in np.flatnonzero(sim.on)
    )
    return (
        f'{{"frame":{sim.frame},"t_ms":{sim.frame * 100},"period":"{sim.period.value}",'
        f'"ball":{{"x":{bx:.2f},"y":{by:.2f},"z":{bz:.2f},"owner_id":{owner}}},'
        f'"players":[{players}]}}\n'
    )


def _write_lines(path: Path, lines: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.writelines(lines)


def _gzip(src: Path) -> None:
    """Compress with mtime=0 so the .gz is byte-identical for the same seed."""
    with (
        src.open("rb") as fin,
        src.with_suffix(src.suffix + ".gz").open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as fout,
    ):
        shutil.copyfileobj(fin, fout)


def simulate(
    seed: int, out_dir: Path, period_s: float = 45 * 60, compress: bool = False
) -> MatchSim:
    roster = build_roster(seed, period_length_ms=round(period_s * 1000))
    sim = MatchSim(roster, seed, period_s=period_s)
    install(sim)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "tracking.jsonl").open("w", encoding="utf-8", newline="\n") as tracking:
        sim.run(lambda s: tracking.write(_frame_line(s)))
    _write_lines(out_dir / "meta.jsonl", [roster.meta.model_dump_json() + "\n"])
    _write_lines(
        out_dir / "players.jsonl", [p.profile.model_dump_json() + "\n" for p in roster.players]
    )
    _write_lines(
        out_dir / "events.jsonl",
        [e.model_dump_json(exclude_none=True) + "\n" for e in sim.events],
    )
    if compress:
        _gzip(out_dir / "tracking.jsonl")
    return sim


def summary(sim: MatchSim) -> dict[str, object]:
    counts: dict[str, int] = {}
    for e in sim.events:
        counts[e.type.value] = counts.get(e.type.value, 0) + 1
    passes = [e for e in sim.events if e.type.value == "pass"]
    ok = sum(1 for e in passes if e.outcome and e.outcome.value == "success")
    scripted = sorted({t for e in sim.events for t in e.tags if t.startswith("scripted:")})
    return {
        "score": f"Riverside {sim.score[0]} - {sim.score[1]} Hillton",
        "events": counts,
        "pass_accuracy": round(ok / max(1, len(passes)), 3),
        "scripted": scripted,
    }
