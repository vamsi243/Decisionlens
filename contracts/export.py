"""Export JSON Schema for every record to contracts/schema/.

Writes one file per record plus `contracts.json`, a bundle the web app turns into TS types.
Run: uv run python -m contracts.export
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from contracts import (
    CalibrationReport,
    Event,
    IntensityPoint,
    KeyMoment,
    MarkingAdvice,
    MatchMeta,
    MatchStats,
    OptionSet,
    Overlay,
    PlayerDecisions,
    PlayerProfile,
    PlayerStats,
    TrackingFrame,
    WhatIf,
    WorkloadState,
)
from contracts.stream import Hello, MomentAnalysis, ReplayStatus

SCHEMA_DIR = Path(__file__).parent / "schema"

RECORDS: dict[str, type[BaseModel]] = {
    "MatchMeta": MatchMeta,
    "PlayerProfile": PlayerProfile,
    "TrackingFrame": TrackingFrame,
    "Event": Event,
    "WorkloadState": WorkloadState,
    "KeyMoment": KeyMoment,
    "OptionSet": OptionSet,
    "WhatIf": WhatIf,
    "Overlay": Overlay,
    "MatchStats": MatchStats,
    "IntensityPoint": IntensityPoint,
    "CalibrationReport": CalibrationReport,
    "ReplayStatus": ReplayStatus,
    "MomentAnalysis": MomentAnalysis,
    "Hello": Hello,
    "PlayerStats": PlayerStats,
    "PlayerDecisions": PlayerDecisions,
    "MarkingAdvice": MarkingAdvice,
}


class Contracts(BaseModel):
    """Bundle model so one schema carries every record as a shared $def."""

    match_meta: MatchMeta
    player_profile: PlayerProfile
    tracking_frame: TrackingFrame
    event: Event
    workload_state: WorkloadState
    key_moment: KeyMoment
    option_set: OptionSet
    what_if: WhatIf
    overlay: Overlay
    match_stats: MatchStats
    intensity_point: IntensityPoint
    calibration_report: CalibrationReport
    replay_status: ReplayStatus
    moment_analysis: MomentAnalysis
    hello: Hello
    player_stats: PlayerStats
    player_decisions: PlayerDecisions
    marking_advice: MarkingAdvice


def _dump(path: Path, schema: dict[str, object]) -> None:
    text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")  # LF on every OS


def export(out_dir: Path = SCHEMA_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, model in RECORDS.items():
        path = out_dir / f"{name}.json"
        _dump(path, model.model_json_schema(mode="serialization"))
        written.append(path)
    bundle = out_dir / "contracts.json"
    _dump(bundle, Contracts.model_json_schema(mode="serialization"))
    written.append(bundle)
    return written


if __name__ == "__main__":
    for p in export():
        print(f"wrote {p.relative_to(Path.cwd()) if p.is_relative_to(Path.cwd()) else p}")
