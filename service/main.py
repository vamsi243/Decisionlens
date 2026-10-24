"""FastAPI entry point: REST controls + WebSocket stream for the Decision Lens board."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contracts import (
    IntensityPoint,
    KeyMoment,
    MatchMeta,
    MatchStats,
    Overlay,
    PlayerProfile,
    WorkloadState,
)
from contracts.stream import Hello, MomentAnalysis, ReplayStatus, Speed, StreamMessageType
from service.adapters.ws_publisher import encode
from service.factory import Adapters, build_adapters
from service.pipeline import Job, Pipeline, analysis_worker
from service.settings import get_settings

log = logging.getLogger("decision_lens")


class Runtime:
    """Everything the endpoints need, created in the lifespan."""

    adapters: Adapters
    pipeline: Pipeline
    queue: asyncio.Queue[Job]
    tasks: list[asyncio.Task[Any]]
    ready: asyncio.Event


rt = Runtime()


async def _run_replay() -> None:
    src, pipe = rt.adapters.source, rt.pipeline
    while True:
        pkt = await src.next_packet()
        if pkt is None:  # full time: tell the boards, then wait for play / seek
            await rt.adapters.publisher.publish(StreamMessageType.STATUS, src.status())
            await asyncio.sleep(0.2)
            continue
        try:
            await pipe.handle(pkt)
        except Exception:
            log.exception("frame %s failed", pkt.frame)


async def _precompute() -> None:
    """Warm the analysis cache so key-moment cards appear instantly on replay."""
    for job in rt.pipeline.precompute_jobs():
        await rt.queue.put(job)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    rt.adapters = build_adapters(settings)
    rt.queue = asyncio.Queue()
    rt.pipeline = Pipeline(rt.adapters.source, rt.adapters.store, rt.adapters.publisher, rt.queue)
    await asyncio.to_thread(rt.pipeline.warm_up)
    rt.tasks = [
        asyncio.create_task(_run_replay()),
        asyncio.create_task(analysis_worker(rt.queue, rt.adapters.store, rt.adapters.publisher)),
    ]
    if settings.precompute_analysis:
        rt.tasks.append(asyncio.create_task(_precompute()))
    if settings.replay_autoplay:
        rt.adapters.source.play()
    try:
        yield
    finally:
        for t in rt.tasks:
            t.cancel()
        for t in rt.tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t


app = FastAPI(title="Decision Lens", version="0.4.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "run_mode": get_settings().run_mode}


@app.get("/")
def hello() -> dict[str, str]:
    return {"message": "Decision Lens: every moment, every option, every fan."}


class MatchInfo(BaseModel):
    meta: MatchMeta
    status: ReplayStatus


@app.get("/match")
async def match() -> MatchInfo:
    return MatchInfo(meta=rt.adapters.source.meta, status=rt.adapters.source.status())


@app.get("/players")
async def players() -> list[PlayerProfile]:
    return rt.adapters.source.players


@app.get("/moments")
async def moments(all: bool = False) -> list[KeyMoment]:
    """Key moments detected so far; `all=true` lists every moment in the replay (scrubber)."""
    if all:
        return [d.moment for d in rt.pipeline.all_detected]
    return rt.adapters.store.moments(until_ms=rt.adapters.source.status().t_ms)


@app.get("/moments/{moment_id}/analysis")
async def moment_analysis(moment_id: str) -> MomentAnalysis:
    a = rt.adapters.store.analysis(moment_id)
    if a is None:
        raise HTTPException(404, "analysis not ready")
    return a


@app.get("/stats")
async def stats() -> MatchStats:
    return rt.pipeline.stats()


@app.get("/workload")
async def workload() -> list[WorkloadState]:
    return rt.pipeline.workload()


@app.get("/intensity")
async def intensity() -> list[IntensityPoint]:
    return rt.pipeline.state.intensity.series()


@app.get("/overlays/{overlay_id}")
async def overlay(overlay_id: str) -> Overlay:
    o = rt.adapters.store.overlay(overlay_id)
    if o is None:
        raise HTTPException(404, "no such overlay")
    return o


# --- replay controls --------------------------------------------------------------------------


class SeekBody(BaseModel):
    t_ms: int


class SpeedBody(BaseModel):
    speed: Speed


async def _status() -> ReplayStatus:
    s = rt.adapters.source.status()
    await rt.adapters.publisher.publish(StreamMessageType.STATUS, s)
    return s


@app.post("/replay/play")
async def play() -> ReplayStatus:
    rt.adapters.source.play()
    return await _status()


@app.post("/replay/pause")
async def pause() -> ReplayStatus:
    rt.adapters.source.pause()
    return await _status()


@app.post("/replay/seek")
async def seek(body: SeekBody) -> ReplayStatus:
    rt.adapters.source.seek(body.t_ms)
    return await _status()


@app.post("/replay/speed")
async def speed(body: SpeedBody) -> ReplayStatus:
    rt.adapters.source.set_speed(body.speed)
    return await _status()


# --- WebSocket ---------------------------------------------------------------------------------


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    src, store = rt.adapters.source, rt.adapters.store
    status = src.status()
    hello_msg = Hello(
        meta=src.meta,
        players=src.players,
        status=status,
        moments=store.moments(until_ms=status.t_ms),
        stats=store.stats() or rt.pipeline.stats(),
        frame=src.packet(status.frame).data,
    )
    assert rt.adapters.ws is not None
    await rt.adapters.ws.serve(websocket, encode(StreamMessageType.HELLO, hello_msg))
