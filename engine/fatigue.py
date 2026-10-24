"""Fatigue model, shared by the generator (to slow players) and the engine (to explain them).

Per tick, for every player:

    intensity    = max(0, speed - 5)^1.3                 (only running above 5 m/s costs much)
    recent_load  = EWMA(intensity, tau = 5 min)          (what the last few minutes cost)
    fatigue     += 0.07 * intensity * (1 + 0.3 * min(recent_load, 2)) * dt
    fatigue     += 0.008 * dt  while moving (>= 2 m/s)    (the steady cost of playing)
    fatigue     -= 0.008 * dt  while walking (< 2 m/s)    (slow recovery)

Fatigue is 0-100 and turns into multipliers on the physical profile:
speed 1 -> 0.78, acceleration 1 -> 0.70, reaction time 1 -> 1.40 at fatigue 100.
A knock costs a further 10% speed and acceleration.
"""

from __future__ import annotations

import numpy as np

from contracts import Modifiers, PhysicalStatus

LOAD_TAU_S = 300.0
TIRING, FATIGUED = 40.0, 70.0


class FatigueModel:
    def __init__(self, n: int) -> None:
        self.fatigue = np.zeros(n)
        self.recent_load = np.zeros(n)
        self.knocked = np.zeros(n, bool)

    def step(self, speed: np.ndarray, dt: float, active: np.ndarray | None = None) -> None:
        intensity = np.maximum(0.0, speed - 5.0) ** 1.3
        self.recent_load += (intensity - self.recent_load) * (dt / LOAD_TAU_S)
        gain = 0.07 * intensity * (1.0 + 0.3 * np.minimum(self.recent_load, 2.0))
        gain = gain + np.where(speed >= 2.0, 0.008, 0.0)
        recover = np.where(speed < 2.0, 0.008, 0.0)
        delta = (gain - recover) * dt
        if active is not None:
            delta = delta * active
        self.fatigue = np.clip(self.fatigue + delta, 0.0, 100.0)

    def speed_mod(self) -> np.ndarray:
        return (1.0 - 0.0022 * self.fatigue) * np.where(self.knocked, 0.9, 1.0)

    def accel_mod(self) -> np.ndarray:
        return (1.0 - 0.003 * self.fatigue) * np.where(self.knocked, 0.9, 1.0)

    def reaction_mod(self) -> np.ndarray:
        return 1.0 + 0.004 * self.fatigue

    def modifiers(self, i: int) -> Modifiers:
        return modifiers_for(float(self.fatigue[i]), bool(self.knocked[i]))

    def status(self, i: int) -> PhysicalStatus:
        return status_for(float(self.fatigue[i]), bool(self.knocked[i]))


def modifiers_for(fatigue: float, knocked: bool = False) -> Modifiers:
    k = 0.9 if knocked else 1.0
    return Modifiers(
        speed=round(max(0.5, (1.0 - 0.0022 * fatigue) * k), 4),
        accel=round(max(0.5, (1.0 - 0.003 * fatigue) * k), 4),
        reaction=round(min(1.6, 1.0 + 0.004 * fatigue), 4),
    )


def status_for(fatigue: float, knocked: bool = False) -> PhysicalStatus:
    if knocked:
        return PhysicalStatus.KNOCK
    if fatigue >= FATIGUED:
        return PhysicalStatus.FATIGUED
    if fatigue >= TIRING:
        return PhysicalStatus.TIRING
    return PhysicalStatus.FIT
