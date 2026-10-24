"""Kinematics: how long a player or the ball takes to reach a point, and pitch control.

Player arrival (Spearman-style, simplified): the player keeps drifting on their current velocity
for their reaction time, then accelerates from rest at `accel` up to `vmax`:

    d_acc = vmax^2 / (2 a)
    t(d)  = reaction + sqrt(2 d / a)                         if d <= d_acc
          = reaction + vmax / a + (d - d_acc) / vmax         otherwise

Ball flight on the ground decelerates with drag: s(t) = D (1 - e^{-kt}) / (1 - e^{-kT}),
where T is the total flight time. Lofted balls use a smaller k and a parabolic height.

Contests use a logistic on the time difference: P(player first) = sigmoid((t_ball - t_player) / s).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

L, W = 105.0, 68.0
GROUND_K, LOFTED_K = 0.35, 0.25
GROUND_SPEED, LOFTED_SPEED = 11.5, 15.0  # average flight speed, m/s
LOFT_DISTANCE = 32.0  # passes longer than this are lofted
TIME_SIGMA = 0.45  # s: spread of the arrival-time logistic
CONTROL_RADIUS = 1.0  # m: a player only needs to get this close to play the ball

FloatArray = np.ndarray


def sigmoid(x: FloatArray | float) -> FloatArray:
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


@dataclass(frozen=True)
class Kinematics:
    """Movement state of n players, already scaled by fatigue modifiers."""

    pos: FloatArray  # (n, 2)
    vel: FloatArray  # (n, 2)
    vmax: FloatArray  # (n,)
    accel: FloatArray  # (n,)
    reaction: FloatArray  # (n,)

    def __len__(self) -> int:
        return len(self.vmax)

    def take(self, idx: FloatArray | list[int] | slice) -> Kinematics:
        return Kinematics(
            self.pos[idx], self.vel[idx], self.vmax[idx], self.accel[idx], self.reaction[idx]
        )

    def jitter(self, rng: np.random.Generator, reaction_sd: float, speed_sd: float) -> Kinematics:
        n = len(self)
        return Kinematics(
            self.pos,
            self.vel,
            self.vmax * np.clip(rng.normal(1.0, speed_sd, n), 0.7, 1.3),
            self.accel * np.clip(rng.normal(1.0, speed_sd, n), 0.7, 1.3),
            np.clip(self.reaction + rng.normal(0.0, reaction_sd, n), 0.05, 0.8),
        )


def arrival_time(k: Kinematics, points: FloatArray, radius: float = CONTROL_RADIUS) -> FloatArray:
    """Time (s) for each player to get within `radius` of each point: shape (n, m)."""
    pts = np.atleast_2d(points)
    start = k.pos + k.vel * k.reaction[:, None]
    d = np.linalg.norm(pts[None, :, :] - start[:, None, :], axis=2)
    d = np.maximum(0.0, d - radius)
    vmax = k.vmax[:, None]
    a = k.accel[:, None]
    d_acc = vmax**2 / (2.0 * a)
    t = np.where(d <= d_acc, np.sqrt(2.0 * d / a), vmax / a + (d - d_acc) / vmax)
    return np.asarray(t + k.reaction[:, None], dtype=float)


def flight_params(distance: float, lofted: bool) -> tuple[float, float]:
    """Total flight time T and drag k for a pass of `distance` metres."""
    speed = LOFTED_SPEED if lofted else GROUND_SPEED
    return max(0.3, distance / speed), (LOFTED_K if lofted else GROUND_K)


def ball_time_at(frac: FloatArray, T: float, k: float) -> FloatArray:
    """Time for the ball to cover fraction `frac` of its path (inverse of the drag curve)."""
    f = np.clip(np.asarray(frac, dtype=float), 0.0, 1.0)
    return np.asarray(-np.log(1.0 - f * (1.0 - math.exp(-k * T))) / k, dtype=float)


def ball_frac_at(t: FloatArray, T: float, k: float) -> FloatArray:
    t = np.clip(np.asarray(t, dtype=float), 0.0, T)
    return (1.0 - np.exp(-k * t)) / (1.0 - math.exp(-k * T))


def kick_speed(distance: float, T: float, k: float) -> float:
    """Initial ball speed (m/s) implied by the drag curve."""
    return distance * k / (1.0 - math.exp(-k * T))


def pitch_control(
    attack: Kinematics, defend: Kinematics, points: FloatArray, sigma: float = TIME_SIGMA
) -> FloatArray:
    """P(attacking team controls each point): logistic on the fastest arrival of each side."""
    ta = arrival_time(attack, points).min(axis=0)
    td = arrival_time(defend, points).min(axis=0)
    return sigmoid((td - ta) / sigma)


def grid(nx: int = 21, ny: int = 14) -> FloatArray:
    """Cell centres of an nx x ny grid over the pitch: shape (nx * ny, 2), x-major."""
    xs = (np.arange(nx) + 0.5) * L / nx
    ys = (np.arange(ny) + 0.5) * W / ny
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    return np.stack([gx.ravel(), gy.ravel()], axis=1)
