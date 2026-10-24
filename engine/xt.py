"""A simple expected-threat (xT) grid.

xT(cell) ~ the chance a possession at that cell ends in a goal soon. We build it analytically
(no real-match data): a small base that grows up the pitch plus a share of the open-play xG from
that spot. 16 x 12 cells, team-relative (attacking toward x = 105).
"""

from __future__ import annotations

import numpy as np

from engine.probability import goal_geometry, xg

NX, NY = 16, 12


def _build() -> np.ndarray:
    g = np.zeros((NX, NY))
    for i in range(NX):
        for j in range(NY):
            x = (i + 0.5) * 105.0 / NX
            y = (j + 0.5) * 68.0 / NY
            dist, angle = goal_geometry(x, y)
            g[i, j] = 0.004 + 0.03 * (x / 105.0) ** 2 + 0.55 * xg(dist, angle, 0.0)
    return g


GRID = _build()


def xt(x: float, y: float) -> float:
    """xT at a team-relative point."""
    i = min(NX - 1, max(0, int(x / 105.0 * NX)))
    j = min(NY - 1, max(0, int(y / 68.0 * NY)))
    return float(GRID[i, j])
