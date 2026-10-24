"""Grounding check: every number an agent writes must appear in the engine payload it was given.

We collect every number in the payload (and the usual ways of writing it: a probability 0.43 may
appear as 43, 43%, 0.43 or 43.0) and reject text containing any other number. Numbers inside
payload strings count too, so a driver such as "+12 cm reach" allows 12.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

MINUS = chr(0x2212)  # the typographic minus sign models sometimes write
# A number, optionally signed (including the unicode minus), with a decimal point or comma.
_NUM = re.compile(r"(?<![\w.])[-+" + MINUS + r"]?\d+(?:[.,]\d+)?")


def _parse(raw: str) -> float:
    return abs(float(raw.replace(MINUS, "-").replace(",", ".")))


def numbers_in(text: str) -> list[tuple[str, float]]:
    return [(m.group(0), _parse(m.group(0))) for m in _NUM.finditer(text)]


def _forms(v: float) -> Iterable[float]:
    v = abs(v)
    yield v
    yield round(v)
    yield round(v, 1)
    yield round(v, 2)
    if v <= 1.0:  # probabilities and fractions appear as percentages
        yield round(v * 100)
        yield round(v * 100, 1)
    elif v <= 100.0:  # and percentages as fractions
        yield round(v / 100, 2)
        yield round(v / 100, 3)


def allowed_numbers(payload: Any) -> set[float]:
    out: set[float] = set()

    def walk(x: Any) -> None:
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            out.update(_forms(float(x)))
        elif isinstance(x, str):
            for _, v in numbers_in(x):
                out.update(_forms(v))
        elif isinstance(x, dict):
            for k, v in x.items():
                walk(k)
                walk(v)
        elif isinstance(x, (list, tuple, set)):
            for v in x:
                walk(v)

    walk(payload)
    return out


@dataclass(frozen=True)
class Grounding:
    ok: bool
    offending: tuple[str, ...]


def check(text: str, payload: Any) -> Grounding:
    allowed = allowed_numbers(payload)
    bad = tuple(raw for raw, v in numbers_in(text) if not any(abs(v - a) < 1e-6 for a in allowed))
    return Grounding(ok=not bad, offending=bad)
