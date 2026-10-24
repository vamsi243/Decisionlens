"""Outcome probabilities. Every probability shown in the app comes from this module.

* pass_success   = P(no defender intercepts) x P(receiver gets there) x P(clean execution)
* aerial_win     = arrival x reach-vs-ball-height contest (Bradley-Terry style)
* xg             = logistic(distance, goal-mouth angle, pressure, header, finishing)
* recovery_run   = P(chaser reaches the carrier's path before the carrier does)
* duel_success   = logistic(skill difference), legs scaled by fatigue
* pass_difficulty= 0-100 from (1 - pass_success) and pressure
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from engine.physics import (
    LOFT_DISTANCE,
    TIME_SIGMA,
    Kinematics,
    arrival_time,
    ball_time_at,
    flight_params,
    sigmoid,
)

GOAL_Y_LOW, GOAL_Y_HIGH = 30.34, 37.66
LANE_SAMPLES = np.linspace(0.2, 1.0, 9)
INTERCEPT_MARGIN = 0.4  # s: a defender must be set this long before the ball arrives
LANE_WEIGHT = 0.85  # even a defender who gets there first does not always win it
EXEC_BIAS = 3.6


def pressure_from_distance(d: float) -> float:
    """1 when an opponent is touching distance, 0 beyond 5 m."""
    return float(min(1.0, max(0.0, 1.0 - (d - 0.5) / 4.5)))


def goal_geometry(fx: float, fy: float) -> tuple[float, float]:
    """Distance to goal centre and goal-mouth angle (rad), attacking toward x = 105."""
    dx = max(0.1, 105.0 - fx)
    dist = math.hypot(dx, fy - 34.0)
    angle = abs(math.atan2(GOAL_Y_HIGH - fy, dx) - math.atan2(GOAL_Y_LOW - fy, dx))
    return dist, angle


def xg(
    dist: float,
    angle: float,
    pressure: float,
    header: bool = False,
    finishing: float = 70.0,
) -> float:
    logit = (
        0.2
        - 0.16 * dist
        + 0.9 * angle
        - 1.2 * pressure
        - (1.2 if header else 0.0)
        + (finishing - 70.0) / 40.0
    )
    return float(sigmoid(logit))


@dataclass(frozen=True)
class PassEval:
    p: float
    p_lane: float
    p_receive: float
    p_execute: float
    interceptor: int  # index into the defenders passed in (-1 if none)
    intercept_frac: float  # where along the lane the interceptor is most dangerous
    lofted: bool
    flight_time: float


def pass_success(
    start: np.ndarray,
    end: np.ndarray,
    receiver: Kinematics,
    defenders: Kinematics,
    *,
    passing: float,
    pressure: float,
    lofted: bool | None = None,
) -> PassEval:
    start = np.asarray(start, float)
    end = np.asarray(end, float)
    dist = float(np.linalg.norm(end - start))
    lofted = dist > LOFT_DISTANCE if lofted is None else lofted
    T, k = flight_params(dist, lofted)

    # Defenders can only cut out a lofted ball near where it comes down.
    fracs = LANE_SAMPLES[LANE_SAMPLES >= 0.75] if lofted else LANE_SAMPLES
    points = start + (end - start) * fracs[:, None]
    t_ball = ball_time_at(fracs, T, k)
    t_def = arrival_time(defenders, points)  # (n_def, m)
    p_point = sigmoid((t_ball[None, :] - t_def - INTERCEPT_MARGIN) / TIME_SIGMA)
    p_int = p_point.max(axis=1) if len(defenders) else np.zeros(0)
    p_lane = float(np.prod(1.0 - LANE_WEIGHT * p_int))

    t_recv = float(arrival_time(receiver, end[None, :])[0, 0])
    p_receive = float(sigmoid((T + 0.6 - t_recv) / TIME_SIGMA))
    p_execute = float(sigmoid(EXEC_BIAS + (passing - 70.0) / 15.0 - 1.8 * pressure - 0.03 * dist))

    if len(defenders):
        j = int(np.argmax(p_int))
        frac = float(fracs[int(np.argmax(p_point[j]))])
    else:
        j, frac = -1, 1.0
    return PassEval(
        p=p_lane * p_receive * p_execute,
        p_lane=p_lane,
        p_receive=p_receive,
        p_execute=p_execute,
        interceptor=j,
        intercept_frac=frac,
        lofted=lofted,
        flight_time=T,
    )


def pass_difficulty(p_success: float, pressure: float) -> float:
    """0 (routine) to 100 (near impossible)."""
    return round(100.0 * min(1.0, 0.8 * (1.0 - p_success) + 0.2 * pressure), 1)


def aerial_win(
    att: Kinematics,
    att_reach_cm: float,
    att_aerial: float,
    dfd: Kinematics,
    dfd_reach_cm: float,
    dfd_aerial: float,
    landing: np.ndarray,
    ball_height_m: float,
    t_ball: float,
) -> float:
    """P(the attacker wins the header)."""
    pt = np.asarray(landing, float)[None, :]
    arr_a = float(sigmoid((t_ball - arrival_time(att, pt, radius=0.6)[0, 0]) / 0.3))
    arr_d = float(sigmoid((t_ball - arrival_time(dfd, pt, radius=0.6)[0, 0]) / 0.3))
    h = ball_height_m * 100.0
    reach_a = float(sigmoid((att_reach_cm - h) / 12.0))
    reach_d = float(sigmoid((dfd_reach_cm - h) / 12.0))
    wa = arr_a * reach_a * math.exp((att_reach_cm - 250.0) / 40.0 + (att_aerial - 70.0) / 50.0)
    wd = arr_d * reach_d * math.exp((dfd_reach_cm - 250.0) / 40.0 + (dfd_aerial - 70.0) / 50.0)
    wd *= 1.3  # defenders attack the ball facing it
    if wa + wd < 1e-9:
        return 0.5
    return wa / (wa + wd)


def recovery_run(
    chaser: Kinematics,
    carrier: Kinematics,
    danger: np.ndarray,
    carry_factor: float = 0.75,
    samples: int = 12,
) -> float:
    """P(chaser gets within tackling range of the carrier before he reaches `danger`)."""
    start = carrier.pos[0]
    danger = np.asarray(danger, float)
    path = start + (danger - start) * np.linspace(0.0, 1.0, samples)[:, None]
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    t_carrier = cum / max(0.5, float(carrier.vmax[0]) * carry_factor)
    t_chaser = arrival_time(chaser, path, radius=1.5)[0]
    p = sigmoid((t_carrier - t_chaser) / 0.5)
    return float(1.0 - np.prod(1.0 - 0.35 * p))


def duel_success(attacker_skill: float, defender_skill: float, legs: float = 1.0) -> float:
    """P(the first player wins a ground duel); `legs` < 1 for a tired first player."""
    return float(sigmoid((attacker_skill - defender_skill) / 18.0 - 0.15 + 2.0 * (legs - 1.0)))
