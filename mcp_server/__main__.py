"""Standalone MCP server over stdio for MCP clients (VS Code, MCP Inspector and others).

It replays a match file to full time (with every moment analysed) and serves the same tools the
live service mounts at /mcp.

Run: uv run python -m mcp_server [--match data/samples/match_42]
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from mcp_server.context import EngineContext
from mcp_server.server import build_server
from service.adapters.file_replay import FileReplay
from service.adapters.memory_store import MemoryStore
from service.pipeline import Pipeline, analyse


class _Silent:
    async def publish(self, *_: object) -> None: ...
    async def publish_raw(self, *_: object) -> None: ...


def full_time_context(match_dir: Path) -> EngineContext:
    src = FileReplay(match_dir)
    store = MemoryStore()
    pipe = Pipeline(src, store, _Silent())
    pipe.warm_up()
    pipe.restore(src.n_frames)
    for job in pipe.precompute_jobs():
        store.put_moment(job.detected.moment)
        store.put_analysis(analyse(job))
    return EngineContext(pipe, store)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", type=Path, default=Path("data/samples/match_42"))
    a = ap.parse_args()
    server = build_server(full_time_context(a.match))
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
