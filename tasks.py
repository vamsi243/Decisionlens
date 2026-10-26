"""Cross-platform task runner (the Makefile delegates here, so Windows works without make).

Usage: uv run python tasks.py <dev|test|lint|generate|replay|schema> [--seed N]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
WEB = ROOT / "web"


def pnpm(*args: str) -> list[str]:
    exe = shutil.which("pnpm")
    base = [exe] if exe else [shutil.which("corepack") or "corepack", "pnpm"]
    return [*base, *args]


def run(cmd: list[str], cwd: Path = ROOT) -> int:
    print("$", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=cwd)


def dev() -> int:
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "service.main:app", "--reload", "--port", "8000"],
        cwd=ROOT,
    )
    web = subprocess.Popen(pnpm("dev"), cwd=WEB)
    try:
        return web.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        for p in (api, web):
            p.terminate()


def test() -> int:
    return run([sys.executable, "-m", "pytest", "-q"]) or run(pnpm("typecheck"), cwd=WEB)


def lint() -> int:
    return (
        run([sys.executable, "-m", "ruff", "check", "."])
        or run([sys.executable, "-m", "ruff", "format", "--check", "."])
        or run([sys.executable, "-m", "mypy"])
    )


def generate(seed: int) -> int:
    return run([sys.executable, "-m", "generator", "--seed", str(seed), "--gzip"])


def replay() -> int:
    return run([sys.executable, "-m", "uvicorn", "service.main:app", "--port", "8000"])


def calibrate() -> int:
    m = "data/samples/match_42"
    return run([sys.executable, "-m", "engine.calibration", m, "--out", f"{m}/calibration.json"])


def schema() -> int:
    return run([sys.executable, "-m", "contracts.export"]) or run(pnpm("types"), cwd=WEB)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "task", choices=["dev", "test", "lint", "generate", "replay", "schema", "calibrate"]
    )
    parser.add_argument("--seed", type=int, default=42)
    a = parser.parse_args()
    if a.task == "generate":
        return generate(a.seed)
    return {
        "dev": dev,
        "test": test,
        "lint": lint,
        "replay": replay,
        "schema": schema,
        "calibrate": calibrate,
    }[a.task]()


if __name__ == "__main__":
    raise SystemExit(main())
