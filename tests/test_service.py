import asyncio
import collections
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import orjson
import pytest
from fastapi.testclient import TestClient

from contracts import KeyMoment, MatchStats
from contracts.stream import Hello, StreamMessageType
from generator.writer import simulate
from service.adapters.file_replay import FileReplay
from service.adapters.memory_store import MemoryStore
from service.pipeline import Pipeline
from service.settings import get_settings


@pytest.fixture(scope="module")
def short_match(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("short")
    simulate(3, out, period_s=60)  # 2 x 1 minute = 1200 frames
    return out


class Capture:
    """A Publisher that records what it was asked to send."""

    def __init__(self) -> None:
        self.sent: list[tuple[StreamMessageType, Any]] = []

    async def publish(self, kind: StreamMessageType, data: Any) -> None:
        self.sent.append((kind, data))

    async def publish_raw(self, kind: StreamMessageType, raw: bytes) -> None:
        self.sent.append((kind, orjson.loads(raw)))


async def _count_frames(src: FileReplay, seconds: float) -> list[int]:
    frames: list[int] = []
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            pkt = await asyncio.wait_for(src.next_packet(), max(0.01, end - time.monotonic()))
        except TimeoutError:
            break
        if pkt is None:
            break
        frames.append(pkt.frame)
    return frames


@pytest.mark.parametrize("speed", [1, 2, 4, 8])
def test_replay_runs_at_match_speed(short_match: Path, speed: int) -> None:
    async def run() -> list[int]:
        src = FileReplay(short_match, speed=speed)  # type: ignore[arg-type]
        src.play()
        return await _count_frames(src, 1.0)

    frames = asyncio.run(run())
    expected = 10 * speed  # frames per real second
    assert expected * 0.8 <= len(frames) <= expected * 1.2 + 1
    assert frames == list(range(len(frames)))


def test_pause_blocks_and_play_resumes(short_match: Path) -> None:
    async def run() -> tuple[list[int], list[int]]:
        src = FileReplay(short_match, speed=8)
        src.play()
        await _count_frames(src, 0.2)
        src.pause()
        paused = await _count_frames(src, 0.3)
        src.play()
        resumed = await _count_frames(src, 0.3)
        return paused, resumed

    paused, resumed = asyncio.run(run())
    assert paused == []
    assert len(resumed) > 10


def test_seek_and_speed_change(short_match: Path) -> None:
    async def run() -> tuple[int, bool, int]:
        src = FileReplay(short_match, speed=1)
        src.play()
        src.seek(45_000)
        pkt = await src.next_packet()
        assert pkt is not None
        src.set_speed(8)
        n = len(await _count_frames(src, 0.5))
        return pkt.frame, pkt.after_seek, n

    frame, after_seek, n = asyncio.run(run())
    assert frame == 450 and after_seek
    assert n >= 30  # 8x after the speed change


def test_restore_after_seek_matches_straight_replay(short_match: Path) -> None:
    src = FileReplay(short_match)
    a = Pipeline(src, MemoryStore(), Capture())
    a.warm_up()
    for f in range(700):
        a._process(a.state, src.packet(f))
    b = Pipeline(src, MemoryStore(), Capture())
    b.warm_up()
    b.restore(700)
    assert np.allclose(a.state.workload.distance, b.state.workload.distance)
    assert a.state.stats.c == b.state.stats.c
    assert a.state.frame == b.state.frame == 699


def test_handle_publishes_frames_events_and_stats(short_match: Path) -> None:
    src, cap, store = FileReplay(short_match), Capture(), MemoryStore()
    pipe = Pipeline(src, store, cap)
    pipe.warm_up()

    async def run() -> None:
        for f in range(60):
            await pipe.handle(src.packet(f))

    asyncio.run(run())
    kinds = collections.Counter(k for k, _ in cap.sent)
    assert kinds[StreamMessageType.FRAME] == 60
    assert kinds[StreamMessageType.STATS] == 6
    assert kinds[StreamMessageType.WORKLOAD] == 2
    stats = store.stats()
    assert isinstance(stats, MatchStats)
    assert sum(t.possession for t in stats.teams) == pytest.approx(1.0, abs=0.01)


# --- the API ------------------------------------------------------------------------------------


@pytest.fixture
def client(short_match: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("MATCH_DIR", str(short_match))
    monkeypatch.setenv("REPLAY_AUTOPLAY", "false")
    monkeypatch.setenv("PRECOMPUTE_ANALYSIS", "false")
    get_settings.cache_clear()
    from service.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_rest_endpoints(client: TestClient) -> None:
    m = client.get("/match").json()
    assert m["meta"]["teams"][0]["name"] == "Riverside FC"
    assert m["status"]["playing"] is False and m["status"]["duration_ms"] == 120_000
    assert len(client.get("/players").json()) == 32
    assert client.get("/moments").json() == []
    for k in client.get("/moments", params={"all": "true"}).json():
        KeyMoment.model_validate(k)
    assert client.get("/overlays/nope").status_code == 404
    assert client.post("/replay/speed", json={"speed": 4}).json()["speed"] == 4
    assert client.post("/replay/speed", json={"speed": 3}).status_code == 422
    assert client.post("/replay/seek", json={"t_ms": 30_000}).json()["t_ms"] == 29_900


def test_websocket_streams_hello_then_frames(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        hello = orjson.loads(ws.receive_text())
        assert hello["type"] == "hello"
        Hello.model_validate(hello["data"])
        client.post("/replay/speed", json={"speed": 8})
        client.post("/replay/play")
        kinds: collections.Counter[str] = collections.Counter()
        frames = []
        while kinds["frame"] < 20:
            msg = orjson.loads(ws.receive_text())
            kinds[msg["type"]] += 1
            if msg["type"] == "frame":
                frames.append(msg["data"]["frame"])
        assert frames == sorted(frames)
        assert kinds["status"] >= 1
        client.post("/replay/pause")


def test_seek_republishes_the_full_picture(short_match: Path) -> None:
    src, cap = FileReplay(short_match), Capture()
    pipe = Pipeline(src, MemoryStore(), cap)
    pipe.warm_up()
    pkt = src.packet(733)  # not on any publishing cadence
    pkt.after_seek = True
    asyncio.run(pipe.handle(pkt))
    kinds = {k for k, _ in cap.sent}
    expected = {StreamMessageType.STATS, StreamMessageType.WORKLOAD, StreamMessageType.INTENSITY}
    assert expected <= kinds


def test_overlays_traces_and_mcp_mount(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATCH_DIR", "data/samples/match_42")
    monkeypatch.setenv("PRECOMPUTE_ANALYSIS", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "")
    monkeypatch.setenv("AGENT_CACHE_PATH", "")
    get_settings.cache_clear()
    from service.main import app

    with TestClient(app) as c:
        n = len(c.get("/moments", params={"all": "true"}).json())
        deadline = time.monotonic() + 60
        cards: list[dict[str, Any]] = []
        while time.monotonic() < deadline and len(cards) < n:
            cards = c.get("/overlays", params={"all": "true"}).json()
            time.sleep(0.2)
        assert n > 0 and len(cards) == n
        assert all(o["grounded"] and o["text"]["analyst"]["en"] for o in cards)
        assert (
            c.get(f"/overlays/{cards[0]['overlay_id']}", params={"lang": "es"}).status_code == 503
        )
        traces = c.get("/agents/traces").json()
        assert len(traces) == n and all(t["steps"] for t in traces)
        init = c.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
            headers={"Accept": "application/json, text/event-stream", "Host": "127.0.0.1:8000"},
        )
        assert init.status_code == 200 and "decision-lens" in init.text

        # Phase 7: replay frames for a moment, heat maps, and the full-time recap on demand
        km = c.get("/moments", params={"all": "true"}).json()[0]
        fr = c.get(f"/moments/{km['moment_id']}/frames").json()
        span = km["frame_range"]
        assert len(fr) == span["end"] - span["start"] + 1 and fr[0]["frame"] == span["start"]
        assert c.get("/moments/nope/frames").status_code == 404
        heat = c.get("/players/RIV_03/heatmap", params={"full": "true"}).json()
        assert (heat["nx"], heat["ny"]) == (21, 14)
        assert abs(sum(map(sum, heat["cells"])) - 1.0) < 0.01
        recap = c.get("/recap").json()
        assert recap["kind"] == "recap" and recap["payload"]["final"]
        assert recap["payload"]["minute"] == 90
        swings = [t["what_if"] for t in recap["payload"]["turning_points"] if "what_if" in t]
        assert swings and swings[0]["with_swap"] - swings[0]["actual"] > 0.2
    get_settings.cache_clear()


def test_live_broadcast_hides_moments_that_have_not_happened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At kick-off of a live broadcast the 87' goal must not be listed or replayable."""
    monkeypatch.setenv("MATCH_DIR", "data/samples/match_42")
    monkeypatch.setenv("PRECOMPUTE_ANALYSIS", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    monkeypatch.setenv("AGENT_CACHE_PATH", "")
    get_settings.cache_clear()
    from service.main import app, rt

    with TestClient(app) as c:
        every = c.get("/moments", params={"all": "true"}).json()
        assert every and rt.adapters.source.status().t_ms < every[-1]["t_ms"]
        monkeypatch.setattr(type(rt.adapters), "live", property(lambda _: True))
        shown = c.get("/moments", params={"all": "true"}).json()
        now = rt.adapters.source.status().t_ms
        assert all(m["t_ms"] <= now for m in shown) and len(shown) < len(every)
        assert c.get(f"/moments/{every[-1]['moment_id']}/frames").status_code == 404
