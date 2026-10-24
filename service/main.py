"""FastAPI entry point: REST controls + WebSocket stream for the Decision Lens board."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint
from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents import templates
from agents.backend import build_backend
from agents.cache import ResponseCache
from agents.copilot import RateLimit, build_copilot, viewer_scope
from agents.orchestrator import Orchestrator
from agents.router import Trigger, route
from agents.translator import Translator
from contracts import (
    IntensityPoint,
    KeyMoment,
    MatchMeta,
    MatchStats,
    Overlay,
    Persona,
    PlayerDecisions,
    PlayerProfile,
    PlayerStats,
    WorkloadState,
)
from contracts.stream import Hello, MomentAnalysis, ReplayStatus, Speed, StreamMessageType
from mcp_server.context import EngineContext
from mcp_server.server import build_server
from service.adapters.ws_publisher import encode
from service.factory import Adapters, build_adapters
from service.pipeline import Job, Pipeline, analyse, analysis_worker
from service.settings import get_settings
from service.telemetry import setup_telemetry

log = logging.getLogger("decision_lens")


class Runtime:
    """Everything the endpoints need, created in the lifespan."""

    adapters: Adapters
    pipeline: Pipeline
    queue: asyncio.Queue[Job]
    tasks: list[asyncio.Task[Any]]
    ctx: EngineContext
    orchestrator: Orchestrator
    translator: Translator
    mcp_app: Any = None


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


async def _on_period_end(e: Any) -> None:
    rt.orchestrator.submit_period_end(e)


async def _precompute() -> None:
    """Warm the analysis cache so key-moment cards appear instantly on replay."""
    for job in rt.pipeline.precompute_jobs():
        await rt.queue.put(job)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_telemetry(settings)
    rt.adapters = await build_adapters(settings)
    rt.queue = asyncio.Queue()
    rt.pipeline = Pipeline(rt.adapters.source, rt.adapters.store, rt.adapters.publisher, rt.queue)
    await asyncio.to_thread(rt.pipeline.warm_up)

    # Agents: engine tools over MCP (mounted at /mcp), the router-driven orchestrator, Translator.
    rt.ctx = EngineContext(rt.pipeline, rt.adapters.store)
    mcp = build_server(rt.ctx)
    rt.mcp_app = mcp.streamable_http_app(streamable_http_path="/", stateless_http=True)
    rt.orchestrator = Orchestrator(
        rt.ctx,
        rt.adapters.store,
        rt.adapters.publisher,
        build_backend(settings, settings.mcp_url),
        settings,
        ResponseCache(
            None, initial=rt.adapters.cache_initial, sink=rt.adapters.cache_sink
        )  # Azure: mirrored to Cosmos DB
        if rt.adapters.cache_sink
        else ResponseCache(Path(settings.agent_cache_path) if settings.agent_cache_path else None),
    )
    rt.translator = Translator(settings)
    rt.pipeline.period_end_hook = _on_period_end

    rt.tasks = [
        asyncio.create_task(_run_replay()),
        asyncio.create_task(
            analysis_worker(
                rt.queue,
                rt.adapters.store,
                rt.adapters.publisher,
                rt.orchestrator.submit_moment,
            )
        ),
        asyncio.create_task(rt.orchestrator.worker()),
        *(asyncio.create_task(job()) for job in rt.adapters.background),
    ]
    if settings.precompute_analysis:
        rt.tasks.append(asyncio.create_task(_precompute()))
    if settings.replay_autoplay and not rt.adapters.live:
        rt.adapters.source.play()
    try:
        async with mcp.session_manager.run():
            yield
    finally:
        for t in rt.tasks:
            t.cancel()
        for t in rt.tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        for close in reversed(rt.adapters.closers):
            with contextlib.suppress(Exception):
                await close()


app = FastAPI(title="Decision Lens", version="0.8.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _mount_copilot() -> None:
    """The match copilot (AG-UI, for the CopilotKit chat) at /copilot, when a model is set up.
    Tools read the engine through `rt.ctx`, which exists once the lifespan has warmed up."""
    settings = get_settings()
    if build_backend(settings, settings.mcp_url) is None:
        return
    add_agent_framework_fastapi_endpoint(
        app,
        build_copilot(lambda: rt.ctx, settings, settings.mcp_url),
        path="/copilot",
        dependencies=[Depends(RateLimit())],
        authorization_scope_resolver=viewer_scope,
    )


_mount_copilot()


async def _mcp(scope: Any, receive: Any, send: Any) -> None:
    """The MCP server is built in the lifespan; this forwards /mcp requests to it."""
    if rt.mcp_app is None:
        raise HTTPException(503, "MCP server not ready")
    await rt.mcp_app(scope, receive, send)


app.mount("/mcp", _mcp)


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


@app.get("/moments/{moment_id}/frames")
async def moment_frames(moment_id: str, step: int = 1) -> list[dict[str, Any]]:
    """The tracking frames around a moment (a few seconds before to a few after), for replays."""
    d = rt.pipeline.detected.get(moment_id)
    if d is None:
        raise HTTPException(404, "no such moment")
    src = rt.adapters.source
    fr = d.moment.frame_range
    last = min(fr.end, src.n_frames - 1)
    return [src.packet(f).data for f in range(fr.start, last + 1, max(1, step))]


@app.get("/players/{player_id}/heatmap")
async def heatmap(player_id: str, full: bool = False) -> dict[str, Any]:
    """Share of time in each 5 m cell (21 x 14), so far or (`full=true`) for the whole match."""
    pipe = rt.pipeline.at_full_time() if full else rt.pipeline
    w = pipe.state.workload
    if player_id not in w.index:
        raise HTTPException(404, "no such player")
    cells = w.heatmap(player_id)
    return {"nx": int(cells.shape[0]), "ny": int(cells.shape[1]), "cells": cells.round(4).tolist()}


@app.get("/players/{player_id}/stats")
async def player_stats(player_id: str) -> PlayerStats:
    """Workload and event counts so far: the hover card on the board."""
    if player_id not in rt.pipeline.team_of:
        raise HTTPException(404, "no such player")
    return await asyncio.to_thread(rt.pipeline.player_stats, player_id)


@app.get("/players/{player_id}/decisions")
async def player_decisions(player_id: str) -> PlayerDecisions:
    """The 2-3 decisions that cost this player most so far, plus their best one (engine-ranked).
    Lines come from templates live and from the Decisions agent after each whistle."""
    if player_id not in rt.pipeline.team_of:
        raise HTTPException(404, "no such player")
    t = rt.pipeline.now_ms()
    items = await asyncio.to_thread(rt.pipeline.player_decisions, player_id, t)
    out = []
    for d in items:
        lines = rt.orchestrator.decision_lines.get(d.decision_id)
        if lines is None:
            f = rt.ctx.decision_facts(d)
            lines = {
                Persona.ANALYST: {"en": templates.decision_analyst(f)},
                Persona.FAN: {"en": templates.decision_fan(f)},
            }
        out.append(
            d.model_copy(
                update={
                    "text": lines,
                    "source": "agents"
                    if d.decision_id in rt.orchestrator.decision_lines
                    else "engine",
                }
            )
        )
    return PlayerDecisions(player_id=player_id, t_ms=t, items=out)


@app.get("/recap")
async def recap() -> Overlay:
    """The full-time recap for the recap page, whatever the live replay is doing (cached)."""
    oid = "ov_recap_full_time"
    existing = rt.adapters.store.overlay(oid)
    if existing is not None and existing.payload.get("final"):
        return existing
    store = rt.adapters.store
    for job in rt.pipeline.precompute_jobs():  # don't wait for the background warm-up
        if store.analysis(job.detected.moment.moment_id) is None:
            store.put_analysis(await asyncio.to_thread(analyse, job))
    ctx = EngineContext(rt.pipeline.at_full_time(), store)
    t_end = rt.adapters.source.n_frames * 100
    ov = await rt.orchestrator.recap(Trigger.FULL_TIME, t_end, ctx)
    ov = ov.model_copy(update={"payload": {**ov.payload, "final": True}})
    rt.adapters.store.put_overlay(ov)
    return ov


@app.get("/stats")
async def stats() -> MatchStats:
    return rt.pipeline.stats()


@app.get("/workload")
async def workload() -> list[WorkloadState]:
    return rt.pipeline.workload()


@app.get("/intensity")
async def intensity() -> list[IntensityPoint]:
    return rt.pipeline.state.intensity.series()


@app.get("/overlays")
async def overlays(all: bool = False) -> list[Overlay]:
    """Cards so far (`all=true`: every card generated for the replay)."""
    until = None if all else rt.adapters.source.status().t_ms
    return rt.adapters.store.overlays(until_ms=until)


@app.get("/overlays/{overlay_id}")
async def overlay(overlay_id: str, lang: str = "en") -> Overlay:
    """A card; `lang` adds a translation via Azure AI Translator (no model call, cached)."""
    o = rt.adapters.store.overlay(overlay_id)
    if o is None:
        raise HTTPException(404, "no such overlay")
    if lang == "en":
        return o
    assert route(Trigger.LANGUAGE_CHANGE)  # router: a language change runs the Translator only
    translated = await rt.translator.overlay(o, lang)
    if translated is None:
        raise HTTPException(503, "translation unavailable (no Translator key configured)")
    return translated


@app.get("/agents/traces")
async def agent_traces() -> list[dict[str, Any]]:
    """Which router steps ran for each trigger and where each text came from."""
    return [
        {"trigger": t.trigger, "target": t.target, "steps": [s.__dict__ for s in t.steps]}
        for t in rt.orchestrator.traces
    ]


# --- replay controls --------------------------------------------------------------------------


class SeekBody(BaseModel):
    t_ms: int


class SpeedBody(BaseModel):
    speed: Speed


def _controls() -> None:
    """A shared live broadcast has no transport controls (viewers replay moments as clips)."""
    if rt.adapters.live:
        raise HTTPException(409, "live broadcast: replay controls are disabled")


@app.get("/config")
async def config() -> dict[str, Any]:
    """What the board should do: live broadcast or local replay, and whether SignalR is on."""
    return {"live": rt.adapters.live, "signalr": rt.adapters.signalr is not None}


@app.get("/negotiate")
async def negotiate() -> dict[str, str]:
    """SignalR client connection info (URL + short-lived token from the managed identity)."""
    if rt.adapters.signalr is None:
        raise HTTPException(404, "SignalR is not configured")
    info: dict[str, str] = await rt.adapters.signalr.negotiate()
    return info


async def _status() -> ReplayStatus:
    s = rt.adapters.source.status()
    await rt.adapters.publisher.publish(StreamMessageType.STATUS, s)
    return s


@app.post("/replay/play")
async def play() -> ReplayStatus:
    _controls()
    rt.adapters.source.play()
    return await _status()


@app.post("/replay/pause")
async def pause() -> ReplayStatus:
    _controls()
    rt.adapters.source.pause()
    return await _status()


@app.post("/replay/seek")
async def seek(body: SeekBody) -> ReplayStatus:
    _controls()
    rt.adapters.source.seek(body.t_ms)
    return await _status()


@app.post("/replay/speed")
async def speed(body: SpeedBody) -> ReplayStatus:
    _controls()
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
