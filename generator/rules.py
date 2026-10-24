"""Stub action probabilities used by the simulator to sample outcomes.

These are deliberately simple. Phase 3 replaces them with the engine's models so the generated
ground truth and the probabilities shown in the app come from the same maths.
"""

from __future__ import annotations

import math

GOAL_Y_LOW, GOAL_Y_HIGH = 30.34, 37.66


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def pressure_from_distance(d: float) -> float:
    """1 when an opponent is touching distance, 0 beyond 5 m."""
    return min(1.0, max(0.0, 1.0 - (d - 0.5) / 4.5))


def goal_geometry(fx: float, fy: float) -> tuple[float, float]:
    """Distance to goal centre and goal-mouth angle (rad), team-relative (goal at fx=105)."""
    dx = max(0.1, 105.0 - fx)
    dist = math.hypot(dx, fy - 34.0)
    angle = abs(math.atan2(GOAL_Y_HIGH - fy, dx) - math.atan2(GOAL_Y_LOW - fy, dx))
    return dist, angle


def xg(dist: float, angle: float, pressure: float, header: bool = False) -> float:
    logit = 0.2 - 0.16 * dist + 0.9 * angle - 1.2 * pressure - (1.2 if header else 0.0)
    return sigmoid(logit)


def pass_success(
    dist: float, lane_clear: float, recv_space: float, pressure: float, passing: float
) -> float:
    logit = (
        1.6
        + 0.38 * min(lane_clear, 6.0)
        + 0.12 * min(recv_space, 8.0)
        - 0.04 * dist
        - 1.3 * pressure
        + (passing - 70.0) / 25.0
    )
    return sigmoid(logit)


def aerial_win(att_reach: float, att_aerial: float, def_reach: float, def_aerial: float) -> float:
    """Probability the attacker wins a header; reach in cm (already fatigue-adjusted)."""
    return sigmoid(((att_reach + 0.4 * att_aerial) - (def_reach + 0.4 * def_aerial)) / 10.0)


def dribble_success(att_skill: float, def_tackle: float) -> float:
    return sigmoid((att_skill - def_tackle) / 18.0 - 0.1)


def tackle_success(def_tackle: float, att_skill: float) -> float:
    return sigmoid((def_tackle - att_skill) / 18.0 - 0.2)
