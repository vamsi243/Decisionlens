"""Calibration: do the engine's probabilities match what happened in the generated match?

For every non-scripted pass, rebuild the frame at the kick, ask the engine for p_success and
compare with the logged outcome. Same for shots (xG vs goals). Reports the Brier score, the
expected calibration error (ECE: average |predicted - observed| across bins, weighted by count)
and a reliability table for the analyst drawer's calibration chart.

Run: uv run python -m engine.calibration data/samples/match_42 [--out calibration.json]
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np

from contracts import CalibrationBin, CalibrationReport, EventType, Outcome
from engine.match import MatchData
from engine.probability import goal_geometry, pass_success, xg


def report(
    model: str, predicted: list[float], observed: list[int], bins: int = 10
) -> CalibrationReport:
    p = np.asarray(predicted, float)
    o = np.asarray(observed, float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    out, ece = [], 0.0
    for lo, hi in itertools.pairwise(edges):
        m = (p >= lo) & ((p < hi) | (hi == 1.0))
        if not m.any():
            continue
        pm, om = float(p[m].mean()), float(o[m].mean())
        ece += m.sum() / len(p) * abs(pm - om)
        out.append(
            CalibrationBin(
                lo=float(lo),
                hi=float(hi),
                count=int(m.sum()),
                predicted=round(pm, 4),
                observed=round(om, 4),
            )
        )
    return CalibrationReport(
        model=model,
        samples=len(p),
        brier=round(float(((p - o) ** 2).mean()), 4) if len(p) else 0.0,
        ece=round(float(ece), 4),
        bins=out,
    )


def pass_predictions(data: MatchData) -> tuple[list[float], list[int]]:
    pred, obs = [], []
    for e in data.events:
        if (
            e.type != EventType.PASS
            or "scripted" in e.tags
            or not (e.start and e.end and e.target_id and e.player_id)
        ):
            continue
        snap = data.snapshot(e.frame_ref)
        if e.player_id not in snap.ids or e.target_id not in snap.ids:
            continue
        ev = pass_success(
            np.array([e.start.x, e.start.y]),
            np.array([e.end.x, e.end.y]),
            snap.kin([snap.idx(e.target_id)]),
            snap.kin(snap.opponents(e.player_id)),
            passing=data.profile(e.player_id).skill.passing,
            pressure=e.pressure or 0.0,
            lofted="lofted" in e.tags,
        )
        pred.append(ev.p)
        obs.append(int(e.outcome == Outcome.SUCCESS))
    return pred, obs


def shot_predictions(data: MatchData) -> tuple[list[float], list[int]]:
    pred, obs = [], []
    home = data.meta.teams[0].team_id
    for e in data.events:
        if e.type != EventType.SHOT or "scripted" in e.tags or e.start is None:
            continue
        x, y = (e.start.x, e.start.y) if e.team_id == home else (105 - e.start.x, 68 - e.start.y)
        dist, angle = goal_geometry(x, y)
        fin = data.profile(e.player_id).skill.finishing if e.player_id else 70.0
        pred.append(xg(dist, angle, e.pressure or 0.0, "header" in e.tags, fin))
        obs.append(int(e.outcome == Outcome.SUCCESS))
    return pred, obs


def calibrate(data: MatchData) -> list[CalibrationReport]:
    return [
        report("pass_success", *pass_predictions(data)),
        report("xg", *shot_predictions(data), bins=5),
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("match_dir", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    reports = calibrate(MatchData.load(a.match_dir))
    for r in reports:
        print(f"{r.model}: n={r.samples} brier={r.brier} ece={r.ece}")
        for b in r.bins:
            print(
                f"  {b.lo:.1f}-{b.hi:.1f}  n={b.count:4d}  "
                f"predicted={b.predicted:.3f}  observed={b.observed:.3f}"
            )
    if a.out:
        a.out.write_text(
            json.dumps([r.model_dump() for r in reports], indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
