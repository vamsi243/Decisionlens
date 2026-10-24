"""Azure adapters exercised with in-process doubles (no Azure needed)."""

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from contracts import EventType
from contracts.stream import StreamMessageType
from generator.writer import simulate
from service.adapters.cosmos import CosmosStore
from service.adapters.event_hubs import (
    FRAMES_PER_EVENT,
    EventHubsBroadcaster,
    EventHubsSource,
    MatchClock,
    decode_chunk,
    encode_chunk,
)
from service.adapters.file_replay import FileReplay
from service.adapters.signalr import HybridPublisher, SignalRPublisher
from service.adapters.ws_publisher import WebSocketPublisher
from service.factory import build_adapters
from service.settings import Settings
from tests.factories import key_moment, overlay


@pytest.fixture(scope="module")
def archive_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("arch")
    simulate(5, out, period_s=30)  # 600 frames
    return out


@pytest.fixture
def archive(archive_dir: Path) -> FileReplay:
    return FileReplay(archive_dir)


# --- Event Hubs -----------------------------------------------------------------------------


def test_match_clock_loops_on_wall_time() -> None:
    clock = MatchClock(600, now=lambda: 125.0)  # 1250 frames since the epoch
    assert clock.frame() == 1250 % 600 == 50
    assert clock.seconds_until(60) == pytest.approx(1.0)
    assert clock.seconds_until(40) == 0.0  # already played


def test_chunks_round_trip(archive: FileReplay) -> None:
    frame = next(f for f, evs in sorted(archive.events_by_frame.items()) if evs)
    pkts = [archive.packet(frame + i) for i in range(FRAMES_PER_EVENT)]
    back = decode_chunk(encode_chunk(pkts))
    assert [p.frame for p in back] == [p.frame for p in pkts]
    assert back[0].data == pkts[0].data
    assert [e.event_id for e in back[0].events] == [e.event_id for e in pkts[0].events]


class FakeProducer:
    def __init__(self) -> None:
        self.bodies: list[bytes] = []

    async def create_batch(self, partition_id: str) -> Any:
        sent = self.bodies

        class Batch:
            def add(self, ev: Any) -> None:
                sent.append(b"".join(ev.body))

        return Batch()

    async def send_batch(self, batch: Any) -> None: ...


def test_broadcaster_streams_consecutive_seconds(
    archive: FileReplay, monkeypatch: pytest.MonkeyPatch
) -> None:
    t = [0.0]
    clock = MatchClock(archive.n_frames, now=lambda: t[0])
    prod = FakeProducer()
    caster = EventHubsBroadcaster(archive, prod, clock)
    real_sleep = asyncio.sleep

    async def fake_sleep(seconds: float) -> None:  # time passes exactly as the caster asks
        t[0] += seconds
        await real_sleep(0)

    monkeypatch.setattr("service.adapters.event_hubs.asyncio.sleep", fake_sleep)

    async def run() -> None:
        task = asyncio.create_task(caster.run())
        while len(prod.bodies) < 5:
            await real_sleep(0.001)
        task.cancel()

    asyncio.run(run())
    frames = [p.frame for body in prod.bodies for p in decode_chunk(body)]
    assert frames[:50] == list(range(50))  # one second per event, no gaps, on the clock
    assert t[0] == pytest.approx(len(prod.bodies), abs=1.0)


def test_live_source_restores_on_join_and_wrap(archive: FileReplay) -> None:
    clock = MatchClock(archive.n_frames, now=lambda: 10_000.0)  # everything is "due"
    src = EventHubsSource(archive, consumer=None, clock=clock)
    src.feed(encode_chunk([archive.packet(f) for f in range(300, 310)]))
    src.feed(encode_chunk([archive.packet(f) for f in range(0, 10)]))  # the loop wraps

    async def take(n: int) -> list[tuple[int, bool]]:
        out = []
        for _ in range(n):
            p = await src.next_packet()
            assert p is not None
            out.append((p.frame, p.after_seek))
        return out

    got = asyncio.run(take(20))
    assert got[0] == (300, True) and got[1] == (301, False)  # joined mid-match
    assert got[10] == (0, True)  # wrapped: restore from kick-off
    st = src.status()
    assert st.live and st.playing and st.speed == 1
    assert src.packet(5).frame == 5  # random access comes from the archive


# --- Cosmos DB --------------------------------------------------------------------------------


class FakeContainer:
    def __init__(self, docs: list[dict[str, Any]] | None = None) -> None:
        self.docs = {d["id"]: d for d in docs or []}
        self.upserts = 0

    def query_items(self, query: str, parameters: list[dict[str, Any]], partition_key: str) -> Any:
        m = parameters[0]["value"]
        docs = [d for d in self.docs.values() if d["match_id"] == m]

        async def gen() -> Any:
            for d in docs:
                yield d

        return gen()

    async def upsert_item(self, doc: dict[str, Any]) -> None:
        self.upserts += 1
        self.docs[doc["id"]] = json.loads(json.dumps(doc))


def test_cosmos_store_writes_through_and_hydrates() -> None:
    c = FakeContainer()

    async def first_run() -> None:
        store = CosmosStore(c, "match_42")
        await store.start()
        store.put_moment(key_moment())
        store.put_moment(key_moment())  # replays re-detect moments: stored once
        store.put_overlay(overlay())
        store.put_cache("k|1", "cached text")
        await store.flush()
        await store.aclose()

    asyncio.run(first_run())
    assert c.upserts == 3
    assert all(":" in d["id"] and "/" not in d["id"] for d in c.docs.values())

    async def wake_up() -> CosmosStore:
        store = CosmosStore(c, "match_42")
        await store.hydrate()
        return store

    s2 = asyncio.run(wake_up())
    assert [m.moment_id for m in s2.moments()] == [key_moment().moment_id]
    assert s2.overlay(overlay().overlay_id) == overlay()
    assert s2.cache == {"k|1": "cached text"}
    assert asyncio.run(_other_match(c)) == 0


async def _other_match(c: FakeContainer) -> int:
    s = CosmosStore(c, "match_7")
    await s.hydrate()
    return len(s.moments())


# --- SignalR ----------------------------------------------------------------------------------


class FakeCredential:
    def __init__(self) -> None:
        self.calls = 0

    async def get_token(self, scope: str) -> Any:
        self.calls += 1
        assert scope == "https://signalr.azure.com/.default"

        class Tok:
            token = "entra-token"
            expires_on = 4_000_000_000

        return Tok()


def test_signalr_broadcast_and_negotiate() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path.endswith(":generateToken"):
            return httpx.Response(200, json={"token": "client-token"})
        return httpx.Response(202, json={})

    cred = FakeCredential()
    sr = SignalRPublisher(
        "https://sigr.service.signalr.net/",
        "decisionlens",
        cred,
        transport=httpx.MockTransport(handler),
    )

    async def run() -> dict[str, str]:
        await sr.start()
        await sr.publish(StreamMessageType.MOMENT, key_moment())
        await sr.publish_raw(StreamMessageType.FRAME, b"{}")  # never over SignalR
        for _ in range(50):
            if sr.sent:
                break
            await asyncio.sleep(0.01)
        neg = await sr.negotiate()
        await sr.aclose()
        return neg

    neg = asyncio.run(run())
    send = seen[0]
    assert send.url.path == "/api/hubs/decisionlens/:send"
    assert send.url.params["api-version"] == "2024-12-01"
    assert send.headers["Authorization"] == "Bearer entra-token"
    body = json.loads(send.content)
    assert body["target"] == "message"
    assert json.loads(body["arguments"][0])["type"] == "moment"
    assert neg == {
        "url": "https://sigr.service.signalr.net/client/?hub=decisionlens",
        "accessToken": "client-token",
    }
    assert seen[1].url.params["minutesToExpire"] == "60"
    assert cred.calls == 1  # the Entra token is cached


def test_hybrid_routes_by_rate() -> None:
    class Rec:
        def __init__(self) -> None:
            self.kinds: list[StreamMessageType] = []

        async def publish(self, kind: StreamMessageType, data: Any) -> None:
            self.kinds.append(kind)

        async def publish_raw(self, kind: StreamMessageType, raw: bytes) -> None:
            self.kinds.append(kind)

    ws, sr = Rec(), Rec()
    hp = HybridPublisher(ws, sr)  # type: ignore[arg-type]

    async def run() -> None:
        for k in StreamMessageType:
            await hp.publish(k, {})
        await hp.publish_raw(StreamMessageType.FRAME, b"{}")

    asyncio.run(run())
    assert set(sr.kinds) == {
        StreamMessageType.MOMENT,
        StreamMessageType.ANALYSIS,
        StreamMessageType.OVERLAY,
        StreamMessageType.STATUS,
        StreamMessageType.INTENSITY,
    }
    assert StreamMessageType.FRAME in ws.kinds and StreamMessageType.STATS in ws.kinds


# --- factory -----------------------------------------------------------------------------------


def test_azure_mode_without_services_falls_back_to_a_looping_replay(archive_dir: Path) -> None:
    s = Settings(_env_file=None, run_mode="azure", match_dir=str(archive_dir))

    async def run() -> tuple[bool, bool, bool]:
        a = await build_adapters(s)
        try:
            return a.live, a.source.status().playing, isinstance(a.publisher, WebSocketPublisher)
        finally:
            for close in a.closers:
                await close()

    live, playing, ws = asyncio.run(run())
    assert not live and playing and ws


def test_live_source_has_no_controls(archive: FileReplay) -> None:
    src = EventHubsSource(archive, consumer=None)
    src.seek(1000)
    src.set_speed(8)
    src.pause()
    assert src.status().playing and src.status().speed == 1
    assert any(
        e.type == EventType.PERIOD_START for evs in archive.events_by_frame.values() for e in evs
    )
