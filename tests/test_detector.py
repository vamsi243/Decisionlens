import collections
from pathlib import Path

import numpy as np
import pytest

from contracts import MomentType
from engine.detector import Detected, MomentDetector
from engine.match import MatchData

SAMPLE = Path("data/samples/match_42")


@pytest.fixture(scope="module")
def run() -> tuple[MatchData, list[Detected]]:
    d = MatchData.load(SAMPLE)
    det = MomentDetector(d.meta, d.players)
    by_frame = collections.defaultdict(list)
    for e in d.events:
        by_frame[e.frame_ref].append(e)
    found: list[Detected] = []
    for f in range(d.n_frames):
        on = np.flatnonzero(~np.isnan(d.pos[f, :, 0]))
        o = int(d.owner[f])
        found += det.on_frame(
            f,
            [d.ids[i] for i in on],
            d.pos[f, on],
            d.vel[f, on],
            d.ball[f],
            d.ids[o] if o >= 0 else None,
            d.fatigue[f],
            d.knocked[f],
        )
        for e in by_frame.get(f, []):
            found += det.on_event(e)
    return d, found


def test_every_scripted_moment_is_flagged_with_the_right_type(
    run: tuple[MatchData, list[Detected]],
) -> None:
    data, found = run
    by_event = {x.moment.event_id: x.moment.type for x in found}
    for e in data.events:
        tag = next((t for t in e.tags if t.startswith("scripted:")), None)
        if tag:
            assert by_event.get(e.event_id) == MomentType(tag.split(":")[1]), tag


def test_few_false_positives(run: tuple[MatchData, list[Detected]]) -> None:
    _, found = run
    counts = collections.Counter(x.moment.type for x in found)
    assert counts[MomentType.LINE_BREAKING_PASS] <= 3
    assert counts[MomentType.PRESS_TURNOVER] <= 3
    assert counts[MomentType.AERIAL_DUEL] <= 3
    assert sum(counts.values()) <= 25


def test_moments_are_analysable_and_ids_stable(run: tuple[MatchData, list[Detected]]) -> None:
    _, found = run
    ids = [x.moment.moment_id for x in found]
    assert len(ids) == len(set(ids))
    for x in found:
        if x.moment.type != MomentType.FATIGUE_ALERT:
            assert x.spec is not None and x.snapshot is not None, x.moment.moment_id
            assert x.moment.players[0] in x.snapshot.ids
        assert x.moment.moment_id == f"km_{x.moment.t_ms // 100:05d}_{x.moment.type.value}"
