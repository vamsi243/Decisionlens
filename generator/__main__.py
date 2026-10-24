"""CLI: uv run python -m generator --seed 42 [--out DIR] [--minutes 90] [--gzip]"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from generator.writer import simulate, summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a synthetic Decision Lens match.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--minutes", type=float, default=90.0, help="match length (scripts need 90)")
    ap.add_argument("--gzip", action="store_true", help="also write tracking.jsonl.gz")
    a = ap.parse_args()
    out = a.out or Path("data/samples") / f"match_{a.seed}"
    t0 = time.perf_counter()
    sim = simulate(a.seed, out, period_s=a.minutes * 30.0, compress=a.gzip)
    info = summary(sim)
    info["seconds"] = round(time.perf_counter() - t0, 1)
    info["out"] = str(out)
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
