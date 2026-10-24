"""The per-frame pipeline: engine metrics -> state -> publish; key moments -> analysis queue.

Everything the pipeline accumulates (workload, stats, intensity, detector) lives in `LiveState`.
A warm-up pass over a replay stores a copy of it every match minute, so a seek restores the
nearest checkpoint and fast-forwards at most 599 frames instead of replaying from kick-off.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from dataclasses import dataclass, field

import numpy as np

from contracts import KeyMoment, MatchMeta, MatchStats, PlayerProfile, WorkloadState
from contracts.stream import MomentAnalysis, StreamMessageType
from engine.detector import Detected, MomentDetector
from engine.metrics import IntensityTracker, StatsTracker, WorkloadTracker
from engine.moments import evaluate
from engine.options import option_set
from engine.whatif import default_swap, what_if
from service.ports import FramePacket, Publisher, StateStore, StreamSource

log = logging.getLogger("decision_lens.pipeline")

CHECKPOINT_EVERY = 600  # frames (one match minute)
STATS_EVERY = 10  # frames
WORKLOAD_EVERY = 50
INTENSITY_EVERY = 600


@dataclass
class LiveState:
    workload: WorkloadTracker
    stats: StatsTracker
    intensity: IntensityTracker
    detector: MomentDetector
    appeared: set[str] = field(default_factory=set)
    on_ids: list[str] = field(default_factory=list)
    frame: int = -1

    @classmethod
    def fresh(cls, meta: MatchMeta, players: list[PlayerProfile]) -> LiveState:
        ids = [p.player_id for p in players]
        finishing = {p.player_id: p.skill.finishing for p in players}
        return cls(
            workload=WorkloadTracker(ids),
            stats=StatsTracker(meta, finishing),
            intensity=IntensityTracker(meta, finishing),
            detector=MomentDetector(meta, players),
        )


@dataclass
class Job:
    detected: Detected
    bench: list[str]


def analyse(job: Job) -> MomentAnalysis:
    """Engine analysis for one moment: the option map and a what-if swap (CPU, run in a thread)."""
    d = job.detected
    mid = d.moment.moment_id
    options = what = None
    if d.snapshot is not None and d.options_actor and d.options_actor in d.snapshot.ids:
        options = option_set(d.snapshot, d.options_actor, mid, chosen=d.chosen)
    if d.snapshot is not None and d.spec is not None:
        try:
            evaluate(d.snapshot, d.spec)
            swap = default_swap(d.snapshot, d.spec, job.bench)
            what = what_if(d.snapshot, d.spec, mid, swap)
        except (KeyError, ValueError) as exc:  # a player left the pitch, unsupported kind, ...
            log.warning("what-if skipped for %s: %s", mid, exc)
    return MomentAnalysis(moment=d.moment, options=options, what_if=what)


class Pipeline:
    def __init__(
        self,
        source: StreamSource,
        store: StateStore,
        publisher: Publisher,
        queue: asyncio.Queue[Job] | None = None,
    ) -> None:
        self.source = source
        self.store = store
        self.publisher = publisher
        self.queue = queue
        self.meta = source.meta
        self.players = source.players
        self.team_of = {p.player_id: p.team_id for p in self.players}
        self.state = LiveState.fresh(self.meta, self.players)
        self.checkpoints: dict[int, LiveState] = {}
        self.all_detected: list[Detected] = []
        self.warm_bench: dict[str, list[str]] = {}  # moment id -> bench at that moment

    # ------------------------------------------------------------------ pure state update
    def _process(self, st: LiveState, pkt: FramePacket) -> list[Detected]:
        d = pkt.data
        ids = [p["id"] for p in d["players"]]
        pos = np.array([[p["x"], p["y"]] for p in d["players"]], float)
        vel = np.array([[p["vx"], p["vy"]] for p in d["players"]], float)
        ball = np.array([d["ball"]["x"], d["ball"]["y"], d["ball"]["z"]], float)
        owner = d["ball"]["owner_id"]
        t_ms = int(d["t_ms"])

        before = st.workload.hsr_total
        st.workload.update(ids, pos, vel)
        st.intensity.add_hsr(t_ms, st.workload.hsr_total - before)
        st.stats.update_frame(owner)
        st.appeared.update(ids)
        st.on_ids = ids
        found = st.detector.on_frame(
            pkt.frame,
            ids,
            pos,
            vel,
            ball,
            owner,
            st.workload.fatigue.fatigue,
            st.workload.fatigue.knocked,
        )
        for e in pkt.events:
            if e.type.value == "knock" and e.player_id:
                st.workload.knock(e.player_id)
            st.stats.update_event(e)
            st.intensity.update_event(e)
            found += st.detector.on_event(e)
        st.frame = pkt.frame
        return found

    def bench(self, st: LiveState, team_id: str | None) -> list[str]:
        return [
            p.player_id
            for p in self.players
            if p.team_id == team_id and p.player_id not in st.appeared
        ]

    # ------------------------------------------------------------------ warm-up & seeking
    def warm_up(self) -> None:
        """Replay the whole match silently: checkpoints for seeking + every moment up front."""
        st = LiveState.fresh(self.meta, self.players)
        for f in range(self.source.n_frames):
            if f % CHECKPOINT_EVERY == 0:
                self.checkpoints[f] = copy.deepcopy(st)
            for d in self._process(st, self.source.packet(f)):
                self.all_detected.append(d)
                self.warm_bench[d.moment.moment_id] = self.bench(st, d.moment.team_id)

    def precompute_jobs(self) -> list[Job]:
        return [Job(d, self.warm_bench.get(d.moment.moment_id, [])) for d in self.all_detected]

    def restore(self, frame: int) -> None:
        """State as it was just before `frame` was processed."""
        base = max((k for k in self.checkpoints if k <= frame), default=None)
        if base is None:
            self.state, start = LiveState.fresh(self.meta, self.players), 0
        else:
            self.state, start = copy.deepcopy(self.checkpoints[base]), base
        for f in range(start, frame):
            self._process(self.state, self.source.packet(f))
        self.store.reset_live()

    # ------------------------------------------------------------------ live
    def stats(self) -> MatchStats:
        km: dict[str, float] = {}
        w = self.state.workload
        for i, pid in enumerate(w.ids):
            km[self.team_of[pid]] = km.get(self.team_of[pid], 0.0) + float(w.distance[i]) / 1000
        return self.state.stats.snapshot(max(0, self.state.frame) * 100, km)

    def workload(self) -> list[WorkloadState]:
        t = max(0, self.state.frame) * 100
        return [self.state.workload.state(pid, t) for pid in self.state.on_ids]

    async def handle(self, pkt: FramePacket) -> None:
        if pkt.after_seek:
            self.restore(pkt.frame)
        found = self._process(self.state, pkt)
        pub = self.publisher
        await pub.publish_raw(StreamMessageType.FRAME, pkt.raw)
        for e in pkt.events:
            await pub.publish(StreamMessageType.EVENT, e)
        if pkt.frame % STATS_EVERY == 0:
            s = self.stats()
            self.store.put_stats(s)
            await pub.publish(StreamMessageType.STATS, s)
        if pkt.frame % WORKLOAD_EVERY == 0:
            await pub.publish(StreamMessageType.WORKLOAD, self.workload())
        if pkt.frame % INTENSITY_EVERY == 0:
            await pub.publish(StreamMessageType.INTENSITY, self.state.intensity.series())
        for d in found:
            await self._moment(d)

    async def _moment(self, d: Detected) -> None:
        m: KeyMoment = d.moment
        self.store.put_moment(m)
        await self.publisher.publish(StreamMessageType.MOMENT, m)
        ready = self.store.analysis(m.moment_id)
        if ready is not None:
            await self.publisher.publish(StreamMessageType.ANALYSIS, ready)
        elif self.queue is not None and (d.spec or d.options_actor):
            await self.queue.put(Job(d, self.bench(self.state, m.team_id)))


async def analysis_worker(
    queue: asyncio.Queue[Job], store: StateStore, publisher: Publisher
) -> None:
    """Consume key moments: compute the engine analysis off the event loop, store, publish."""
    while True:
        job = await queue.get()
        try:
            mid = job.detected.moment.moment_id
            if store.analysis(mid) is None:
                store.put_analysis(await asyncio.to_thread(analyse, job))
            ready = store.analysis(mid)
            if ready is not None:
                await publisher.publish(StreamMessageType.ANALYSIS, ready)
        except Exception:
            log.exception("analysis failed")
        finally:
            queue.task_done()
