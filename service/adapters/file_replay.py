"""FileReplay: streams a generated match from JSONL at 1x / 2x / 4x / 8x, with pause and seek."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections import defaultdict
from pathlib import Path

import orjson

from contracts import Event, MatchMeta, Period, PlayerProfile
from contracts.stream import ReplayStatus, Speed
from engine.match import iter_tracking, read_jsonl
from service.ports import FramePacket

FRAME_S = 0.1
MAX_LAG_S = 1.0  # if we fall further behind than this, drop the backlog instead of bursting


class FileReplay:
    def __init__(self, match_dir: Path | str, speed: Speed = 1) -> None:
        d = Path(match_dir)
        self.meta = MatchMeta.model_validate_json(read_jsonl(d / "meta.jsonl")[0])
        self.players = [
            PlayerProfile.model_validate_json(x) for x in read_jsonl(d / "players.jsonl")
        ]
        self.events_by_frame: dict[int, list[Event]] = defaultdict(list)
        for line in read_jsonl(d / "events.jsonl"):
            e = Event.model_validate_json(line)
            self.events_by_frame[e.frame_ref].append(e)
        self.lines = [line.rstrip(b"\r\n") for line in iter_tracking(d)]
        self.n_frames = len(self.lines)
        self._frame = 0  # next frame to emit
        self._playing = False
        self._speed: Speed = speed
        self._after_seek = False
        self._wake = asyncio.Event()
        self._clock_t = time.monotonic()
        self._clock_frame = 0

    # ------------------------------------------------------------------ data
    def packet(self, frame: int) -> FramePacket:
        raw = self.lines[frame]
        return FramePacket(
            frame=frame,
            raw=raw,
            data=orjson.loads(raw),
            events=list(self.events_by_frame.get(frame, ())),
        )

    async def next_packet(self) -> FramePacket | None:
        while True:
            if self._frame >= self.n_frames:
                self._playing = False
                return None
            if not self._playing:
                await self._sleep(None)
                continue
            due = self._clock_t + (self._frame - self._clock_frame) * FRAME_S / self._speed
            now = time.monotonic()
            if due - now > 0:
                if await self._sleep(due - now):
                    continue  # a control changed something: re-evaluate
            elif now - due > MAX_LAG_S:
                self._resync()
            pkt = self.packet(self._frame)
            pkt.after_seek, self._after_seek = self._after_seek, False
            self._frame += 1
            return pkt

    async def _sleep(self, seconds: float | None) -> bool:
        """Wait for `seconds` or until a control wakes us. True if woken."""
        try:
            if seconds is None:
                await self._wake.wait()
            else:
                await asyncio.wait_for(self._wake.wait(), seconds)
        except TimeoutError:
            return False
        self._wake.clear()
        return True

    # ------------------------------------------------------------------ controls
    def _resync(self) -> None:
        self._clock_t = time.monotonic()
        self._clock_frame = self._frame

    def _poke(self) -> None:
        self._resync()
        self._wake.set()

    def play(self) -> None:
        if self._frame >= self.n_frames:
            self.seek(0)
        self._playing = True
        self._poke()

    def pause(self) -> None:
        self._playing = False
        self._poke()

    def seek(self, t_ms: int) -> None:
        self._frame = max(0, min(self.n_frames - 1, t_ms // 100))
        self._after_seek = True
        self._poke()

    def set_speed(self, speed: Speed) -> None:
        self._speed = speed
        self._poke()

    def status(self) -> ReplayStatus:
        frame = max(0, self._frame - 1) if self._frame else 0
        t_ms = frame * 100
        return ReplayStatus(
            playing=self._playing,
            speed=self._speed,
            frame=frame,
            t_ms=t_ms,
            period=Period.FIRST_HALF if t_ms < self.meta.period_length_ms else Period.SECOND_HALF,
            duration_ms=self.n_frames * 100,
        )

    async def aclose(self) -> None:
        with contextlib.suppress(Exception):
            self._wake.set()
