import shutil
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from contracts import EventType, Modifiers, MomentType, Outcome, PhysicalStatus
from engine.calibration import calibrate
from engine.fatigue import FatigueModel, modifiers_for, status_for
from engine.match import MatchData
from engine.metrics import IntensityTracker, StatsTracker, WorkloadTracker
from engine.moments import spec_for_event
from engine.montecarlo import prob_range
from engine.options import option_set
from engine.physics import (
    Kinematics,
    arrival_time,
    ball_frac_at,
    ball_time_at,
    pitch_control,
)
from engine.probability import (
    aerial_win,
    duel_success,
    goal_geometry,
    pass_difficulty,
    pass_success,
    recovery_run,
    xg,
)
from engine.whatif import default_swap, swap_custom, what_if
from engine.xt import GRID

SAMPLE = Path("data/samples/match_42")


def kin(*players: tuple[float, float, float, float]) -> Kinematics:
    """players: (x, y, vmax, reaction), at rest, accel 4."""
    a = np.array(players, float)
    return Kinematics(
        pos=a[:, :2],
        vel=np.zeros((len(a), 2)),
        vmax=a[:, 2],
        accel=np.full(len(a), 4.0),
        reaction=a[:, 3],
    )


NOBODY = Kinematics(np.zeros((0, 2)), np.zeros((0, 2)), np.zeros(0), np.zeros(0), np.zeros(0))


# --- physics ---------------------------------------------------------------------------------


def test_arrival_time_closed_form() -> None:
    k = Kinematics(
        np.zeros((1, 2)), np.zeros((1, 2)), np.array([8.0]), np.array([4.0]), np.array([0.2])
    )
    # d_acc = 64 / 8 = 8 m; 20 m -> 0.2 + 8/4 + 12/8 = 3.7 s
    assert arrival_time(k, np.array([[20.0, 0.0]]), radius=0.0)[0, 0] == pytest.approx(3.7)
    near = arrival_time(k, np.array([[0.5, 0.0]]), radius=1.0)[0, 0]
    assert near == pytest.approx(0.2)


def test_arrival_time_grows_with_distance_and_fatigue() -> None:
    k = kin((0, 0, 9, 0.2), (0, 0, 7, 0.3))
    t = arrival_time(k, np.array([[5.0, 0.0], [25.0, 0.0]]))
    assert t[0, 0] < t[0, 1]
    assert (t[0] < t[1]).all()


def test_ball_flight_inverse() -> None:
    fr = np.linspace(0, 1, 11)
    assert ball_frac_at(ball_time_at(fr, 2.0, 0.35), 2.0, 0.35) == pytest.approx(fr)
    assert ball_time_at(np.array([1.0]), 2.0, 0.35)[0] == pytest.approx(2.0)


def test_pitch_control_owner_and_symmetry() -> None:
    a, d = kin((50, 34, 8, 0.2)), kin((60, 34, 8, 0.2))
    assert pitch_control(a, d, np.array([[50.0, 34.0]]))[0] > 0.9
    assert pitch_control(a, d, np.array([[55.0, 34.0]]))[0] == pytest.approx(0.5)


# --- probabilities ---------------------------------------------------------------------------


def test_pass_success_open_vs_blocked() -> None:
    start, end = np.array([40.0, 34.0]), np.array([60.0, 34.0])
    recv = kin((60, 34, 8, 0.2))
    open_ = pass_success(start, end, recv, NOBODY, passing=75, pressure=0.0).p
    blocked = pass_success(start, end, recv, kin((50, 34.5, 8, 0.2)), passing=75, pressure=0.0).p
    assert open_ > 0.9
    assert blocked < open_ - 0.3


def test_lofted_pass_clears_a_midfield_defender() -> None:
    start, end = np.array([30.0, 34.0]), np.array([70.0, 34.0])
    recv, mid = kin((70, 34, 8, 0.2)), kin((50, 34.5, 8, 0.2))
    ground = pass_success(start, end, recv, mid, passing=75, pressure=0.0, lofted=False).p
    lofted = pass_success(start, end, recv, mid, passing=75, pressure=0.0, lofted=True).p
    assert lofted > ground


def test_pass_success_drops_with_pressure_and_bounds() -> None:
    start, end = np.array([40.0, 34.0]), np.array([55.0, 40.0])
    recv = kin((55, 40, 8, 0.2))
    calm = pass_success(start, end, recv, NOBODY, passing=70, pressure=0.0).p
    hassled = pass_success(start, end, recv, NOBODY, passing=70, pressure=1.0).p
    assert 0.0 <= hassled < calm <= 1.0


def test_pass_difficulty() -> None:
    assert pass_difficulty(1.0, 0.0) == 0.0
    assert pass_difficulty(0.0, 1.0) == 100.0
    assert pass_difficulty(0.5, 0.2) < pass_difficulty(0.4, 0.2)


def test_xg_shape() -> None:
    d1, a1 = goal_geometry(94.0, 34.0)
    d2, a2 = goal_geometry(80.0, 34.0)
    d3, a3 = goal_geometry(100.0, 5.0)
    assert xg(d1, a1, 0.0) > xg(d2, a2, 0.0) > 0.0
    assert xg(d1, a1, 0.0) > xg(d3, a3, 0.0)
    assert xg(d1, a1, 0.0, header=True) < xg(d1, a1, 0.0)
    assert xg(d1, a1, 1.0) < xg(d1, a1, 0.0)
    assert xg(d1, a1, 0.0, finishing=90) > xg(d1, a1, 0.0, finishing=50)
    dg, ag = goal_geometry(105.0, 34.0)  # on the line
    assert 0.0 < xg(dg, ag, 0.0) < 1.0


def test_aerial_win_reach_and_arrival() -> None:
    landing = np.array([5.0, 30.0])
    a, d = kin((5, 30, 8, 0.2)), kin((5.5, 30, 8, 0.2))
    tall = aerial_win(a, 280, 85, d, 230, 50, landing, 2.4, 1.0)
    short = aerial_win(a, 230, 50, d, 280, 85, landing, 2.4, 1.0)
    assert tall > 0.8 > 0.2 > short
    far = aerial_win(kin((40, 30, 8, 0.2)), 280, 85, d, 250, 70, landing, 2.4, 1.0)
    assert far < 0.1
    even = aerial_win(a, 255, 70, d, 255, 70, landing, 2.4, 1.0)
    assert even < 0.5  # the defender attacks the ball facing it


def test_recovery_run_speed_matters() -> None:
    carrier = kin((50, 30, 9, 0.2))
    danger = np.array([20.0, 30.0])
    fast = recovery_run(kin((55, 31, 10, 0.2)), carrier, danger)
    slow = recovery_run(kin((55, 31, 7, 0.3)), carrier, danger)
    hopeless = recovery_run(kin((95, 31, 9, 0.2)), carrier, danger)
    assert fast > slow > hopeless >= 0.0
    assert hopeless < 0.05


def test_duel_success() -> None:
    assert duel_success(80, 60) > duel_success(60, 80)
    assert duel_success(70, 70, legs=0.8) < duel_success(70, 70)


def test_xt_grid_rises_toward_goal() -> None:
    centre = GRID[:, GRID.shape[1] // 2]
    assert (np.diff(centre) > 0).all()
    assert GRID.max() < 0.6


# --- fatigue & workload ----------------------------------------------------------------------


def test_fatigue_rises_sprinting_and_recovers_slowly() -> None:
    m = FatigueModel(2)
    for _ in range(600):  # one minute
        m.step(np.array([8.0, 1.0]), 0.1)
    assert m.fatigue[0] > 15 > m.fatigue[1]
    peak = m.fatigue[0]
    for _ in range(600):
        m.step(np.array([1.0, 1.0]), 0.1)
    assert peak - 1.0 < m.fatigue[0] < peak  # recovery is slow


def test_modifiers_and_status_stay_in_contract() -> None:
    for f in (0, 39.9, 40, 69.9, 70, 100):
        Modifiers.model_validate(modifiers_for(f, knocked=True).model_dump())
    assert status_for(10) == PhysicalStatus.FIT
    assert status_for(50) == PhysicalStatus.TIRING
    assert status_for(80) == PhysicalStatus.FATIGUED
    assert status_for(10, knocked=True) == PhysicalStatus.KNOCK
    assert modifiers_for(100).speed < modifiers_for(0).speed == 1.0


def test_workload_distance_hsr_and_sprints() -> None:
    w = WorkloadTracker(["A", "B"])
    for f in range(31):  # A runs at 8 m/s for 3 s, B walks at 1.5 m/s
        w.update(
            ["A", "B"],
            np.array([[0.8 * f, 10.0], [0.15 * f, 20.0]]),
            np.array([[8.0, 0], [1.5, 0]]),
        )
    a, b = w.state("A", 3000), w.state("B", 3000)
    assert a.distance_m == pytest.approx(24.0, abs=0.1)
    assert a.hsr_m == pytest.approx(24.0, abs=0.1)
    assert a.sprints == 1
    assert b.hsr_m == 0 and b.sprints == 0
    assert w.heatmap("A").sum() == pytest.approx(1.0)


# --- the sample match ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def data() -> MatchData:
    return MatchData.load(SAMPLE)


def test_loader_falls_back_to_gzip(tmp_path: Path) -> None:
    for name in ("meta.jsonl", "players.jsonl", "events.jsonl", "tracking.jsonl.gz"):
        shutil.copy(SAMPLE / name, tmp_path / name)
    d = MatchData.load(tmp_path)
    assert d.n_frames == 54_000
    assert len(d.frame(100).players) == 22


def test_stats_match_a_recount_of_raw_events(data: MatchData) -> None:
    st = StatsTracker(data.meta)
    for e in data.events:
        st.update_event(e)
    for o in data.owner:
        st.update_frame(data.players[o].player_id if o >= 0 else None)
    snap = st.snapshot(5_400_000)
    for t in snap.teams:
        passes = [e for e in data.events if e.type == EventType.PASS and e.team_id == t.team_id]
        assert t.passes == len(passes)
        assert t.passes_completed == sum(e.outcome == Outcome.SUCCESS for e in passes)
        goals = [e for e in data.events if e.type == EventType.GOAL and e.team_id == t.team_id]
        assert t.goals == len(goals)
    assert sum(t.possession for t in snap.teams) == pytest.approx(1.0, abs=1e-3)


def test_workload_matches_tracking_within_one_percent(data: MatchData) -> None:
    w = WorkloadTracker(data.ids)
    for f in range(data.n_frames):
        on = np.flatnonzero(~np.isnan(data.pos[f, :, 0]))
        w.update([data.ids[i] for i in on], data.pos[f, on], data.vel[f, on])
    steps = np.linalg.norm(np.diff(data.pos.astype(float), axis=0), axis=2)
    direct = np.nansum(steps, axis=0)
    for i, pid in enumerate(data.ids):
        if direct[i] > 0:
            assert w.state(pid, 0).distance_m == pytest.approx(direct[i], rel=0.01)
    # engine fatigue replayed from tracking agrees with the live tracker
    assert w.fatigue.fatigue == pytest.approx(data.fatigue[-1], abs=0.5)


def test_intensity_rises_around_key_moments(data: MatchData) -> None:
    it = IntensityTracker(data.meta)
    hsr = WorkloadTracker(data.ids)
    for f in range(data.n_frames):
        on = np.flatnonzero(~np.isnan(data.pos[f, :, 0]))
        before = hsr.hsr_total
        hsr.update([data.ids[i] for i in on], data.pos[f, on], data.vel[f, on])
        it.add_hsr(f * 100, hsr.hsr_total - before)
    for e in data.events:
        it.update_event(e)
    series = it.series()
    assert len(series) == 18
    median = float(np.median([p.index for p in series]))
    for e in data.events:
        if any(t.startswith("scripted:") for t in e.tags):
            assert series[e.t_ms // 300_000].index > median, e.tags


def test_calibration_is_tight(data: MatchData) -> None:
    passes, shots = calibrate(data)
    assert passes.samples > 800
    assert passes.ece < 0.05
    assert passes.brier < 0.2
    assert shots.samples > 5


def _scripted(data: MatchData, kind: MomentType):  # type: ignore[no-untyped-def]
    ev = next(e for e in data.events if f"scripted:{kind.value}" in e.tags)
    assert ev.player_id
    owner = None
    if kind == MomentType.RECOVERY_RUN:
        counter = next(
            e
            for e in reversed(data.events)
            if e.event_id < ev.event_id and e.type == EventType.PASS and e.target_id == ev.player_id
        )
        owner = data.first_owned_after(counter.frame_ref, ev.player_id)
    spec = spec_for_event(kind, ev, data.events, owner)
    return ev, spec, data.snapshot(spec.frame)


@pytest.mark.parametrize("kind", [MomentType.AERIAL_DUEL, MomentType.RECOVERY_RUN])
def test_fresh_specialist_turns_the_moment(data: MatchData, kind: MomentType) -> None:
    _, spec, snap = _scripted(data, kind)
    bench = data.bench(spec.frame, snap.team_of(spec.actor_id))
    w = what_if(snap, spec, f"km_{kind.value}", default_swap(snap, spec, bench), runs=100)
    assert w.actual.p_success < 0.2
    assert w.counterfactual.p_success > w.actual.p_success + 0.15
    assert w.counterfactual.profile.kind.value == "substitute"
    for s in (w.actual, w.counterfactual):
        assert s.range.low <= s.range.median <= s.range.high
    assert any(d.factor == "fatigue" and d.delta < 0 for d in w.drivers)
    assert len(w.ghost_path) == 2


def test_aerial_drivers_name_the_reach(data: MatchData) -> None:
    _, spec, snap = _scripted(data, MomentType.AERIAL_DUEL)
    bench = data.bench(spec.frame, snap.team_of(spec.actor_id))
    w = what_if(snap, spec, "km", default_swap(snap, spec, bench), runs=50)
    reach = next(d for d in w.drivers if d.factor == "jump_reach")
    assert reach.delta > 20 and reach.text.endswith("cm reach")


def test_custom_swap_validates_bounds(data: MatchData) -> None:
    _, spec, snap = _scripted(data, MomentType.AERIAL_DUEL)
    ref, prof, _ = swap_custom(snap, spec.actor_id, {"jump_reach_cm": 280.0}, {})
    assert prof.physical.jump_reach_cm == 280.0 and ref.kind.value == "custom"
    with pytest.raises(ValidationError):
        swap_custom(snap, spec.actor_id, {"max_speed_ms": 20.0}, {})


def test_options_for_line_breaking_pass(data: MatchData) -> None:
    ev, _, _ = _scripted(data, MomentType.LINE_BREAKING_PASS)
    assert ev.player_id
    os_ = option_set(data.snapshot(ev.frame_ref), ev.player_id, "km_lbp", chosen=ev, runs=60)
    assert 1 <= len(os_.options) <= 4
    chosen = [o for o in os_.options if o.chosen]
    assert len(chosen) == 1 and chosen[0].target_id == ev.target_id
    assert chosen[0].xt_gain > 0
    for o in os_.options:
        assert o.range.low <= o.range.high and 0.0 <= o.p_success <= 1.0


def test_monte_carlo_is_deterministic_and_ordered() -> None:
    a, d = kin((50, 34, 8, 0.2)), kin((52, 30, 8, 0.25))

    def fn(rng: np.random.Generator | None) -> float:
        k = a if rng is None else a.jitter(rng, 0.04, 0.05)
        return float(pitch_control(k, d, np.array([[51.0, 32.0]]))[0])

    r1, r2 = prob_range(fn, 7, 200), prob_range(fn, 7, 200)
    assert r1 == r2
    assert r1.low < r1.median < r1.high
