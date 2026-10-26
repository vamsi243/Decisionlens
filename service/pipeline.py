"""The per-frame pipeline: engine metrics -> state -> publish; key moments -> analysis queue.

Everything the pipeline accumulates (workload, stats, intensity, detector) lives in `LiveState`.
A warm-up pass over a replay stores a copy of it every match minute, so a seek restores the
nearest checkpoint and fast-forwards at most 599 frames instead of replaying from kick-off.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import numpy as np

from contracts import (
    Event,
    EventType,
    KeyMoment,
    MatchMeta,
    MatchStats,
    Outcome,
    PlayerDecision,
    PlayerProfile,
    PlayerStats,
    WorkloadState,
)
from contracts.player import MarkingAdvice
from contracts.stream import MomentAnalysis, StreamMessageType
from engine import decisions, matchups
from engine.detector import Detected, MomentDetector
from engine.metrics import IntensityTracker, StatsTracker, WorkloadTracker
from engine.moments import evaluate
from engine.options import option_set
from engine.snapshot import Snapshot
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
    goals: list[Event] = field(default_factory=list)
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
        self.final_state: LiveState | None = None  # the whole match, filled by warm_up()
        self.all_detected: list[Detected] = []
        self.detected: dict[str, Detected] = {}  # moment id -> detection (snapshot + spec)
        self.moment_bench: dict[str, list[str]] = {}  # moment id -> fresh subs at that moment
        self.moment_workload: dict[str, dict[str, WorkloadState]] = {}  # at detection time
        # Player panel: every event, and a snapshot at each on-ball decision (filled by warm_up).
        self.all_events: list[Event] = []
        self.event_index: dict[str, int] = {}
        self.decision_snaps: dict[str, Snapshot] = {}
        self._scored: dict[str, PlayerDecision | None] = {}
        self.finishing = {p.player_id: p.skill.finishing for p in self.players}
        # Called with the period_end event while streaming (half-time / full-time recaps).
        self.period_end_hook: Callable[[Event], Awaitable[None]] | None = None

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
            if e.type == EventType.KNOCK and e.player_id:
                st.workload.knock(e.player_id)
            if e.type == EventType.GOAL:
                st.goals.append(e)
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
            pkt = self.source.packet(f)
            for d in self._process(st, pkt):
                self.all_detected.append(d)
                self._register(st, d)
            for e in pkt.events:
                self.event_index[e.event_id] = len(self.all_events)
                self.all_events.append(e)
                if e.type in decisions.ON_BALL and e.player_id:
                    snap = st.detector.snapshot(f)
                    if snap is not None:
                        self.decision_snaps[e.event_id] = snap
        self.final_state = st

    def at_full_time(self) -> Pipeline:
        """A read-only view of this pipeline as it stands at the final whistle (after warm-up)."""
        view = copy.copy(self)
        view.state = self.final_state or self.state
        return view

    def _register(self, st: LiveState, d: Detected) -> None:
        mid = d.moment.moment_id
        if mid not in self.detected:
            self.detected[mid] = d
            self.moment_bench[mid] = self.bench(st, d.moment.team_id)
            self.moment_workload[mid] = {
                pid: st.workload.state(pid, d.moment.t_ms) for pid in d.moment.players
            }

    def precompute_jobs(self) -> list[Job]:
        return [Job(d, self.moment_bench.get(d.moment.moment_id, [])) for d in self.all_detected]

    def restore(self, frame: int) -> None:
        """State as it was just before `frame` was processed."""
        base = max((k for k in self.checkpoints if k <= frame), default=None)
        if base is None:
            self.state, start = LiveState.fresh(self.meta, self.players), 0
        else:
            self.state, start = copy.deepcopy(self.checkpoints[base]), base
        for f in range(start, frame):
            self._process(self.state, self.source.packet(f))
        # A viewer (or a container waking up) joining mid-match still sees the moments so far.
        for d in self.all_detected:
            if d.moment.t_ms < frame * 100:
                self.store.put_moment(d.moment)
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

    # ------------------------------------------------------------------ player panel
    def now_ms(self) -> int:
        return max(0, self.state.frame) * 100

    def player_stats(self, pid: str) -> PlayerStats:
        """Workload now plus event counts so far, for the hover card."""
        t = self.now_ms()
        w = self.state.workload.state(pid, t)
        c = dict.fromkeys(
            [
                "passes",
                "passes_completed",
                "shots",
                "goals",
                "tackles",
                "tackles_won",
                "interceptions",
                "aerial_duels",
                "aerial_won",
                "dribbles",
                "dribbles_won",
                "fouls",
            ],
            0,
        )
        ok = Outcome.SUCCESS
        for e in self.all_events:
            if e.t_ms > t:
                break
            mine, against = e.player_id == pid, e.target_id == pid
            if e.type == EventType.PASS and mine:
                c["passes"] += 1
                c["passes_completed"] += e.outcome == ok
            elif e.type == EventType.SHOT and mine:
                c["shots"] += 1
            elif e.type == EventType.GOAL and mine:
                c["goals"] += 1
            elif e.type == EventType.TACKLE and mine:
                c["tackles"] += 1
                c["tackles_won"] += e.outcome == ok
            elif e.type == EventType.INTERCEPTION and mine:
                c["interceptions"] += 1
            elif e.type == EventType.AERIAL_DUEL and (mine or against):
                c["aerial_duels"] += 1  # success = the defending-side player (player_id) won
                c["aerial_won"] += (e.outcome == ok) == mine
            elif e.type == EventType.DRIBBLE and mine:
                c["dribbles"] += 1
                c["dribbles_won"] += e.outcome == ok
            elif e.type == EventType.FOUL and mine:
                c["fouls"] += 1
        return PlayerStats(
            player_id=pid,
            t_ms=t,
            on_pitch=pid in self.state.on_ids,
            distance_km=round(w.distance_m / 1000, 2),
            hsr_m=round(w.hsr_m),
            sprints=w.sprints,
            fatigue=round(w.fatigue, 1),
            top_speed_loss_pct=round((1 - w.modifiers.speed) * 100),
            status=w.status,
            **c,
        )

    def player_decisions(self, pid: str, t_ms: int | None = None) -> list[PlayerDecision]:
        """The 2-3 decisions that cost `pid` most so far, plus the best one they got right.
        Nothing after `t_ms` is used, so the panel never gives away what happens next."""
        t = self.now_ms() if t_ms is None else t_ms
        upto = [e for e in self.all_events if e.t_ms <= t]
        scored: list[PlayerDecision] = []
        for i, e in enumerate(upto):
            if e.player_id != pid or e.event_id not in self.decision_snaps:
                continue
            settled = e.t_ms + decisions.WINDOW_MS <= t  # its 15 s have played out: cacheable
            if settled and e.event_id in self._scored:
                d = self._scored[e.event_id]
            else:
                d = decisions.score_on_ball(
                    self.decision_snaps[e.event_id],
                    e,
                    decisions.window(upto, i),
                    self.finishing,
                )
                if settled:
                    self._scored[e.event_id] = d
            if d is not None:
                scored.append(d)
        scored += decisions.defending(
            upto, pid, self.team_of, self.meta.teams[0].team_id, self.finishing
        )
        return decisions.top_decisions(scored)

    def marking_advice(self, attacker_id: str, exclude: list[str] | None = None) -> MarkingAdvice:
        """Who should mark `attacker_id` right now: every opponent on the pitch and every fresh
        substitute, scored with live fatigue (see engine/matchups.py)."""
        st = self.state
        snap = st.detector.snapshot(max(0, st.frame))
        if snap is None or attacker_id not in snap.ids:
            raise ValueError(f"{attacker_id} is not on the pitch")
        att_team = self.team_of[attacker_id]
        team = next(t.team_id for t in self.meta.teams if t.team_id != att_team)
        w = st.workload
        fatigue = {pid: float(w.fatigue.fatigue[w.index[pid]]) for pid in w.ids}
        on = [pid for pid in snap.ids if self.team_of[pid] == team]
        bench = self.bench(st, team)
        y = float(snap.rel(team, snap.pos[snap.idx(attacker_id)])[1])
        return matchups.best_markers(
            attacker_id,
            snap.profiles,
            snap.modifiers,
            fatigue,
            [(pid, True) for pid in on] + [(pid, False) for pid in bench],
            matchups.channel_of(y),
            self.now_ms(),
            exclude or [],
        )

    async def handle(self, pkt: FramePacket) -> None:
        fresh = pkt.after_seek  # boards need the whole picture again after a jump
        if fresh:
            self.restore(pkt.frame)
        found = self._process(self.state, pkt)
        pub = self.publisher
        await pub.publish_raw(StreamMessageType.FRAME, pkt.raw)
        for e in pkt.events:
            await pub.publish(StreamMessageType.EVENT, e)
        if fresh or pkt.frame % STATS_EVERY == 0:
            s = self.stats()
            self.store.put_stats(s)
            await pub.publish(StreamMessageType.STATS, s)
        if fresh or pkt.frame % WORKLOAD_EVERY == 0:
            await pub.publish(StreamMessageType.WORKLOAD, self.workload())
        if fresh or pkt.frame % INTENSITY_EVERY == 0:
            await pub.publish(StreamMessageType.INTENSITY, self.state.intensity.series())
        for d in found:
            self._register(self.state, d)
            await self._moment(d)
        if self.period_end_hook is not None:
            for e in pkt.events:
                if e.type == EventType.PERIOD_END:
                    await self.period_end_hook(e)

    async def _moment(self, d: Detected) -> None:
        m: KeyMoment = d.moment
        self.store.put_moment(m)
        await self.publisher.publish(StreamMessageType.MOMENT, m)
        ready = self.store.analysis(m.moment_id)
        if ready is not None:
            await self.publisher.publish(StreamMessageType.ANALYSIS, ready)
            card = self.store.overlay(f"ov_{m.moment_id}")
            if card is not None:
                await self.publisher.publish(StreamMessageType.OVERLAY, card)
        elif self.queue is not None:
            await self.queue.put(Job(d, self.bench(self.state, m.team_id)))


async def analysis_worker(
    queue: asyncio.Queue[Job],
    store: StateStore,
    publisher: Publisher,
    on_ready: Callable[[MomentAnalysis], None] | None = None,
) -> None:
    """Consume key moments: compute the engine analysis off the event loop, store, publish,
    then hand it on (to the agents' orchestrator)."""
    while True:
        job = await queue.get()
        try:
            mid = job.detected.moment.moment_id
            if store.analysis(mid) is None:
                store.put_analysis(await asyncio.to_thread(analyse, job))
            ready = store.analysis(mid)
            if ready is not None:
                await publisher.publish(StreamMessageType.ANALYSIS, ready)
                if on_ready is not None:
                    on_ready(ready)
        except Exception:
            log.exception("analysis failed")
        finally:
            queue.task_done()
