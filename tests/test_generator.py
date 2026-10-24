import gzip
import json
from pathlib import Path

import pytest

from contracts import Event, MatchMeta, MomentType, PlayerProfile, TrackingFrame
from generator.roster import ROSTERS, build_roster
from generator.script import SCRIPTED_MOMENTS
from generator.sim import MatchSim
from generator.writer import simulate, summary

FILES = ("meta.jsonl", "players.jsonl", "events.jsonl", "tracking.jsonl")


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


@pytest.fixture(scope="module")
def full_match(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, MatchSim]:
    out = tmp_path_factory.mktemp("match_42")
    return out, simulate(42, out, compress=True)


def test_same_seed_identical_files(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    simulate(7, a, period_s=90)
    simulate(7, b, period_s=90)
    for name in FILES:
        assert (a / name).read_bytes() == (b / name).read_bytes(), name


def test_different_seed_differs(tmp_path: Path) -> None:
    simulate(7, tmp_path / "a", period_s=90)
    simulate(8, tmp_path / "b", period_s=90)
    a = (tmp_path / "a" / "tracking.jsonl").read_bytes()
    assert a != (tmp_path / "b" / "tracking.jsonl").read_bytes()


def test_roster_shape() -> None:
    roster = build_roster(42)
    for team in ("RIV", "HIL"):
        squad = [p for p in roster.players if p.profile.team_id == team]
        assert len(squad) == 16
        assert sum(p.profile.starter for p in squad) == 11
        assert len({p.profile.shirt_number for p in squad}) == 16
    assert [t.name for t in roster.meta.teams] == ["Riverside FC", "Hillton United"]
    assert len({e.name for squad in ROSTERS.values() for e in squad}) == 32


def test_files_validate_against_contracts(full_match: tuple[Path, MatchSim]) -> None:
    out, _ = full_match
    MatchMeta.model_validate_json(_lines(out / "meta.jsonl")[0])
    assert len([PlayerProfile.model_validate_json(x) for x in _lines(out / "players.jsonl")]) == 32
    events = [Event.model_validate_json(x) for x in _lines(out / "events.jsonl")]
    assert [e.t_ms for e in events] == sorted(e.t_ms for e in events)
    frames = _lines(out / "tracking.jsonl")
    assert len(frames) == 90 * 60 * 10
    for line in frames[::250]:
        frame = TrackingFrame.model_validate_json(line)
        assert len(frame.players) == 22
    assert json.loads(frames[-1])["t_ms"] == (90 * 60 * 10 - 1) * 100


def test_gzip_matches_plain(full_match: tuple[Path, MatchSim]) -> None:
    out, _ = full_match
    with gzip.open(out / "tracking.jsonl.gz", "rb") as f:
        assert f.read() == (out / "tracking.jsonl").read_bytes()


def test_every_scripted_moment_present(full_match: tuple[Path, MatchSim]) -> None:
    out, _ = full_match
    events = [json.loads(x) for x in _lines(out / "events.jsonl")]
    for moment in SCRIPTED_MOMENTS:
        tagged = [e for e in events if f"scripted:{moment.kind.value}" in e.get("tags", [])]
        assert len(tagged) == 1, moment.kind
        t = tagged[0]["t_ms"] / 1000
        assert moment.start_s <= t <= moment.start_s + 30, (moment.kind, t)


def test_scripted_aerial_duel_is_lost_by_weak_header(full_match: tuple[Path, MatchSim]) -> None:
    out, _ = full_match
    events = [json.loads(x) for x in _lines(out / "events.jsonl")]
    duel = next(
        e for e in events if f"scripted:{MomentType.AERIAL_DUEL.value}" in e.get("tags", [])
    )
    assert (duel["player_id"], duel["target_id"], duel["outcome"]) == ("RIV_02", "HIL_09", "fail")


def test_match_statistics_look_like_football(full_match: tuple[Path, MatchSim]) -> None:
    _, sim = full_match
    info = summary(sim)
    counts = info["events"]
    assert isinstance(counts, dict)
    assert 800 <= counts["pass"] <= 2000
    assert 0.72 <= float(info["pass_accuracy"]) <= 0.92  # type: ignore[arg-type]
    assert 10 <= counts["shot"] <= 45
    assert counts.get("goal", 0) <= 8
    assert counts["substitution"] == 4
    assert counts["knock"] == 1
    for kind in ("tackle", "interception", "aerial_duel", "foul", "cross", "dribble"):
        assert counts.get(kind, 0) > 0, kind


def test_fresh_bench_players_stay_unused(full_match: tuple[Path, MatchSim]) -> None:
    out, _ = full_match
    seen: set[str] = set()
    for line in _lines(out / "tracking.jsonl")[::50]:
        seen.update(p["id"] for p in json.loads(line)["players"])
    assert {"RIV_14", "RIV_15"}.isdisjoint(seen)
    assert {"RIV_16", "RIV_17", "HIL_16", "HIL_17"} <= seen


def test_players_move_at_human_speeds(full_match: tuple[Path, MatchSim]) -> None:
    out, _ = full_match
    top = 0.0
    for line in _lines(out / "tracking.jsonl")[::20]:
        for p in json.loads(line)["players"]:
            top = max(top, (p["vx"] ** 2 + p["vy"] ** 2) ** 0.5)
    assert 7.0 < top <= 11.0


# --- scripted premises: what Phase 3's detector and what-if rely on -------------------------


def _frames_at(out: Path, refs: set[int]) -> dict[int, dict[str, dict[str, float]]]:
    found: dict[int, dict[str, dict[str, float]]] = {}
    for i, line in enumerate(_lines(out / "tracking.jsonl")):
        if i in refs:
            found[i] = {p["id"]: p for p in json.loads(line)["players"]}
    return found


def _scripted(events: list[dict[str, object]], kind: MomentType) -> dict[str, object]:
    return next(e for e in events if f"scripted:{kind.value}" in e.get("tags", []))  # type: ignore[operator]


def test_pass_outcomes_agree_with_tracking(full_match: tuple[Path, MatchSim]) -> None:
    out, _ = full_match
    owners = [json.loads(x)["ball"]["owner_id"] for x in _lines(out / "tracking.jsonl")]
    passes = [json.loads(x) for x in _lines(out / "events.jsonl")]
    passes = [e for e in passes if e["type"] == "pass"]
    wrong = 0
    for e in passes:
        f = e["frame_ref"] + 1
        while f < len(owners) and owners[f] is None:
            f += 1
        if f < len(owners) and (owners[f][:3] == e["team_id"]) != (e["outcome"] == "success"):
            wrong += 1
    assert wrong / len(passes) < 0.01


def test_pass_and_shot_speeds_are_plausible(full_match: tuple[Path, MatchSim]) -> None:
    out, _ = full_match
    events = [json.loads(x) for x in _lines(out / "events.jsonl")]
    passes = sorted(e["ball_speed_ms"] for e in events if e["type"] == "pass")
    shots = sorted(e["ball_speed_ms"] for e in events if e["type"] == "shot")
    assert 10.0 <= passes[len(passes) // 2] <= 20.0
    assert 20.0 <= shots[len(shots) // 2] <= 32.0


def test_scene_geometry(full_match: tuple[Path, MatchSim]) -> None:
    out, _ = full_match
    events = [json.loads(x) for x in _lines(out / "events.jsonl")]
    lb = _scripted(events, MomentType.LINE_BREAKING_PASS)
    pt = _scripted(events, MomentType.PRESS_TURNOVER)
    bc = _scripted(events, MomentType.BIG_CHANCE)
    refs = {int(e["frame_ref"]) for e in (lb, pt, bc)}  # type: ignore[call-overload]
    frames = _frames_at(out, refs)

    x0, x1 = lb["start"]["x"], lb["end"]["x"]  # type: ignore[index]
    bypassed = [
        p
        for pid, p in frames[lb["frame_ref"]].items()  # type: ignore[index]
        if pid.startswith("HIL") and pid != "HIL_01" and x0 < p["x"] < x1
    ]
    assert len(bypassed) >= 3

    cb = frames[pt["frame_ref"]]["RIV_05"]  # type: ignore[index]
    pressers = [
        p
        for pid, p in frames[pt["frame_ref"]].items()  # type: ignore[index]
        if pid.startswith("HIL") and ((p["x"] - cb["x"]) ** 2 + (p["y"] - cb["y"]) ** 2) < 9.0
    ]
    assert len(pressers) >= 2

    st = frames[bc["frame_ref"]]["RIV_09"]  # type: ignore[index]
    gap = min(
        ((p["x"] - st["x"]) ** 2 + (p["y"] - st["y"]) ** 2) ** 0.5
        for pid, p in frames[bc["frame_ref"]].items()  # type: ignore[index]
        if pid.startswith("HIL") and pid != "HIL_01"
    )
    assert gap > 2.5
    assert ((105 - bc["start"]["x"]) ** 2 + (34 - bc["start"]["y"]) ** 2) ** 0.5 < 14  # type: ignore[index]


def test_full_back_is_more_worn_than_the_winger_who_beats_him(
    full_match: tuple[Path, MatchSim],
) -> None:
    out, _ = full_match
    hsr = {"RIV_03": 0.0, "HIL_07": 0.0}
    for line in _lines(out / "tracking.jsonl")[: 71 * 600]:
        for p in json.loads(line)["players"]:
            if p["id"] in hsr:
                speed = (p["vx"] ** 2 + p["vy"] ** 2) ** 0.5
                hsr[p["id"]] += speed * 0.1 if speed > 5.5 else 0.0
    assert hsr["RIV_03"] > 1.3 * hsr["HIL_07"]
