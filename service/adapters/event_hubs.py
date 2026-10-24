"""Event Hubs adapters for RUN_MODE=azure: a broadcaster that streams the match into Event Hubs
and a live StreamSource that consumes it.

The match is a shared live broadcast. Its clock is tied to UTC wall-clock time and loops every
90 minutes, so whenever the app wakes (it scales to zero) the match is wherever it "should" be.
Each Event Hubs event carries one second of play: up to ten tracking frames plus their events.

Seeking and replay speed belong to local mode; in a live broadcast every viewer sees the same
moment, and a key moment is replayed as a personal clip on the viewer's board.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from typing import Any

import orjson

from contracts import Event, Period
from contracts.stream import ReplayStatus, Speed
from service.adapters.file_replay import FileReplay
from service.ports import FramePacket

log = logging.getLogger("decision_lens.event_hubs")

FRAMES_PER_EVENT = 10  # one second of play per Event Hubs event


class MatchClock:
    """Which frame of the looping broadcast is live right now."""

    def __init__(self, n_frames: int, hz: int = 10, now: Callable[[], float] = time.time) -> None:
        self.n_frames = n_frames
        self.hz = hz
        self.now = now

    def frame(self) -> int:
        return int(self.now() * self.hz) % self.n_frames

    def seconds_until(self, frame: int) -> float:
        """Real seconds until `frame` is due (0 if it is due now or overdue)."""
        ahead = (frame - self.frame()) % self.n_frames
        return 0.0 if ahead > self.n_frames // 2 else ahead / self.hz


def encode_chunk(packets: list[FramePacket]) -> bytes:
    """One Event Hubs body: frames forwarded byte-for-byte, events as JSON."""
    return orjson.dumps(
        {
            "frames": [orjson.Fragment(p.raw) for p in packets],
            "events": [
                e.model_dump(mode="json", exclude_none=True) for p in packets for e in p.events
            ],
        }
    )


def decode_chunk(body: bytes) -> list[FramePacket]:
    doc = orjson.loads(body)
    events: dict[int, list[Event]] = {}
    for raw in doc.get("events", []):
        e = Event.model_validate(raw)
        events.setdefault(e.frame_ref, []).append(e)
    out = []
    for fr in doc.get("frames", []):
        f = int(fr["frame"])
        out.append(FramePacket(frame=f, raw=orjson.dumps(fr), data=fr, events=events.get(f, [])))
    return out


class EventHubsBroadcaster:
    """Publishes the archived match into Event Hubs, one second of play per event, on the clock.

    In production a data provider would be the producer; here the replay job runs inside the
    service so the demo needs no extra compute (and it stops when the app scales to zero).
    """

    def __init__(self, archive: FileReplay, producer: Any, clock: MatchClock | None = None) -> None:
        self.archive = archive
        self.producer = producer  # azure.eventhub.aio.EventHubProducerClient
        self.clock = clock or MatchClock(archive.n_frames)

    def chunk_starting(self, frame: int) -> list[FramePacket]:
        n = self.archive.n_frames
        return [self.archive.packet((frame + i) % n) for i in range(FRAMES_PER_EVENT)]

    async def run(self) -> None:
        from azure.eventhub import EventData

        nxt = self.clock.frame() - self.clock.frame() % FRAMES_PER_EVENT
        while True:
            try:
                batch = await self.producer.create_batch(partition_id="0")
                batch.add(EventData(encode_chunk(self.chunk_starting(nxt))))
                await self.producer.send_batch(batch)
            except Exception:
                log.exception("broadcast send failed at frame %d", nxt)
            nxt = (nxt + FRAMES_PER_EVENT) % self.archive.n_frames
            await asyncio.sleep(max(0.05, self.clock.seconds_until(nxt)))


class LoopbackProducer:
    """Stands in for EventHubProducerClient: hands each body straight to a live source.
    `LIVE_SIMULATION=true` uses it to run the live-broadcast path locally, without Azure."""

    def __init__(self, source: EventHubsSource) -> None:
        self.source = source

    async def create_batch(self, partition_id: str) -> _LoopbackBatch:
        return _LoopbackBatch()

    async def send_batch(self, batch: Any) -> None:
        for body in batch:
            self.source.feed(body)


class _LoopbackBatch(list[bytes]):
    def add(self, event: Any) -> None:
        self.append(b"".join(event.body))


class EventHubsSource:
    """Live StreamSource fed by Event Hubs; the local match archive backs warm-up, recap and
    state restoration, so joining mid-match (or the loop wrapping) restores state cleanly."""

    def __init__(self, archive: FileReplay, consumer: Any, clock: MatchClock | None = None) -> None:
        self.archive = archive
        self.consumer = consumer  # azure.eventhub.aio.EventHubConsumerClient
        self.meta = archive.meta
        self.players = archive.players
        self.n_frames = archive.n_frames
        self.clock = clock or MatchClock(archive.n_frames)
        self.queue: asyncio.Queue[FramePacket] = asyncio.Queue(maxsize=600)
        self._last = -1
        self._task: asyncio.Task[None] | None = None
        self._pending: list[FramePacket] = []

    async def start(self) -> None:
        self._task = asyncio.create_task(self._receive())

    async def _receive(self) -> None:
        async def on_event(_: Any, event: Any) -> None:
            if event is None:
                return
            for pkt in decode_chunk(event.body_as_str().encode()):
                if self.queue.full():
                    with contextlib.suppress(asyncio.QueueEmpty):
                        self.queue.get_nowait()
                self.queue.put_nowait(pkt)

        async with self.consumer:
            await self.consumer.receive(
                on_event=on_event, partition_id="0", starting_position="@latest"
            )

    def feed(self, body: bytes) -> None:
        """Push one Event Hubs body (used by tests and by the in-process fallback)."""
        for pkt in decode_chunk(body):
            self.queue.put_nowait(pkt)

    async def next_packet(self) -> FramePacket | None:
        if not self._pending:
            first = await self.queue.get()
            self._pending.append(first)
        pkt = self._pending.pop(0)
        # Frames inside a chunk arrive together; pace them at 10 Hz like a real feed.
        wait = self.clock.seconds_until(pkt.frame)
        if 0 < wait < 2.0:
            await asyncio.sleep(wait)
        pkt.after_seek = pkt.frame != self._last + 1  # joined mid-match or the loop wrapped
        self._last = pkt.frame
        return pkt

    def packet(self, frame: int) -> FramePacket:
        return self.archive.packet(frame)

    def status(self) -> ReplayStatus:
        frame = max(0, self._last)
        t_ms = frame * 100
        return ReplayStatus(
            playing=True,
            speed=1,
            frame=frame,
            t_ms=t_ms,
            period=Period.FIRST_HALF if t_ms < self.meta.period_length_ms else Period.SECOND_HALF,
            duration_ms=self.n_frames * 100,
            live=True,
        )

    # A shared live broadcast has no transport controls.
    def play(self) -> None: ...
    def pause(self) -> None: ...
    def seek(self, t_ms: int) -> None: ...
    def set_speed(self, speed: Speed) -> None: ...

    async def aclose(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
