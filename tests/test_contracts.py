import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from contracts import BallState, Point, ProbRange
from contracts.export import RECORDS, export
from tests import factories


@pytest.mark.parametrize("make", factories.ALL, ids=lambda f: f.__name__)
def test_round_trip(make: Callable[[], BaseModel]) -> None:
    original = make()
    restored = type(original).model_validate_json(original.model_dump_json())
    assert restored == original


@pytest.mark.parametrize("make", factories.ALL, ids=lambda f: f.__name__)
def test_round_trip_via_plain_json(make: Callable[[], BaseModel]) -> None:
    original = make()
    data = json.loads(original.model_dump_json())
    assert type(original).model_validate(data) == original


@pytest.mark.parametrize(("x", "y"), [(-6, 10), (111, 10), (50, -6), (50, 74)])
def test_point_outside_pitch_rejected(x: float, y: float) -> None:
    with pytest.raises(ValidationError):
        Point(x=x, y=y)


def test_point_on_touchline_margin_ok() -> None:
    Point(x=-5, y=73)


@pytest.mark.parametrize("p", [-0.01, 1.01])
def test_probability_bounds(p: float) -> None:
    opt = factories.option_set().options[0].model_dump()
    opt["p_success"] = p
    with pytest.raises(ValidationError):
        type(factories.option_set().options[0]).model_validate(opt)


def test_prob_range_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        ProbRange(median=0.5, low=0.6, high=0.7)


def test_option_set_max_four() -> None:
    os_ = factories.option_set()
    data = os_.model_dump()
    data["options"] = data["options"] * 5
    with pytest.raises(ValidationError):
        type(os_).model_validate(data)


def test_option_set_best_must_exist() -> None:
    data = factories.option_set().model_dump()
    data["best_option_id"] = "nope"
    with pytest.raises(ValidationError):
        type(factories.option_set()).model_validate(data)


def test_match_needs_exactly_one_home_team() -> None:
    data = factories.match_meta().model_dump()
    data["teams"][1]["is_home"] = True
    with pytest.raises(ValidationError):
        type(factories.match_meta()).model_validate(data)


def test_unknown_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        BallState.model_validate({"x": 1, "y": 1, "z": 0, "spin": 3})


def test_fatigue_capped_at_100() -> None:
    data = factories.workload_state().model_dump()
    data["fatigue"] = 101
    with pytest.raises(ValidationError):
        type(factories.workload_state()).model_validate(data)


def test_export_writes_every_schema(tmp_path: Path) -> None:
    written = {p.name for p in export(tmp_path)}
    assert written == {f"{n}.json" for n in RECORDS} | {"contracts.json"}


def test_committed_schema_is_current(tmp_path: Path) -> None:
    export(tmp_path)
    committed = Path("contracts/schema")
    for fresh in tmp_path.iterdir():
        assert (committed / fresh.name).read_text(encoding="utf-8") == fresh.read_text(
            encoding="utf-8"
        ), f"{fresh.name} is stale: run `uv run python tasks.py schema`"
