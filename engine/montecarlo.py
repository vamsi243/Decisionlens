"""Monte Carlo ranges: re-run a probability with jittered reactions and speeds.

Real players are not deterministic: on a given day they react a little faster or slower and
hit slightly different top speeds. Each run jitters every player's reaction time (sd 0.04 s)
and top speed / acceleration (sd 5%), and the 10th-90th percentile of the results is the range.
"""

from __future__ import annotations

import zlib
from collections.abc import Callable

import numpy as np

from contracts import ProbRange

RUNS = 300
REACTION_SD = 0.04
SPEED_SD = 0.05

Evaluator = Callable[[np.random.Generator | None], float]


def seed_for(*parts: object) -> int:
    """Stable seed from ids, so the same moment always gets the same range."""
    return zlib.crc32(":".join(map(str, parts)).encode())


def prob_range(fn: Evaluator, seed: int, runs: int = RUNS) -> ProbRange:
    rng = np.random.default_rng(seed)
    samples = np.array([fn(rng) for _ in range(runs)])
    lo, med, hi = np.percentile(samples, [10, 50, 90])
    return ProbRange(median=round(float(med), 4), low=round(float(lo), 4), high=round(float(hi), 4))
