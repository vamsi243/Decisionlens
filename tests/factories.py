"""Minimal valid instances of every contract, shared by tests."""

from __future__ import annotations

from contracts import (
    ActionKind,
    Archetype,
    BallState,
    Driver,
    Event,
    EventType,
    FrameRange,
    KeyMoment,
    MatchMeta,
    MomentType,
    Option,
    OptionSet,
    Outcome,
    Overlay,
    OverlayKind,
    Period,
    Persona,
    Physical,
    PhysicalStatus,
    PlayerProfile,
    PlayerTrack,
    Point,
    Position,
    ProbRange,
    ProfileKind,
    ProfileRef,
    Scenario,
    Skill,
    TeamColours,
    TeamMeta,
    TrackingFrame,
    WhatIf,
    WorkloadState,
)


def match_meta() -> MatchMeta:
    return MatchMeta(
        match_id="match_42",
        seed=42,
        teams=[
            TeamMeta(
                team_id="RIV",
                name="Riverside FC",
                short_name="RIV",
                formation="4-3-3",
                colours=TeamColours(primary="#1a1a1a", secondary="#ffffff"),
                is_home=True,
            ),
            TeamMeta(
                team_id="HIL",
                name="Hillton United",
                short_name="HIL",
                formation="4-2-3-1",
                colours=TeamColours(primary="#ffffff", secondary="#1a1a1a"),
                is_home=False,
            ),
        ],
    )


def player_profile() -> PlayerProfile:
    return PlayerProfile(
        player_id="RIV_05",
        team_id="RIV",
        name="Tomas Varga",
        shirt_number=5,
        position=Position.CB,
        archetype=Archetype.AERIAL_CB,
        starter=True,
        physical=Physical(
            height_cm=192, max_speed_ms=8.6, accel_ms2=3.4, reaction_s=0.24, jump_reach_cm=268
        ),
        skill=Skill(passing=62, aerial=88, tackle=80, finishing=30),
    )


def tracking_frame() -> TrackingFrame:
    return TrackingFrame(
        frame=120,
        t_ms=12_000,
        period=Period.FIRST_HALF,
        ball=BallState(x=52.5, y=34.0, z=0.1, owner_id="RIV_08"),
        players=[PlayerTrack(id="RIV_08", x=52.0, y=34.2, vx=1.2, vy=-0.3)],
    )


def event() -> Event:
    return Event(
        event_id="ev_000123",
        t_ms=12_000,
        period=Period.FIRST_HALF,
        type=EventType.PASS,
        team_id="RIV",
        player_id="RIV_08",
        start=Point(x=52.0, y=34.2),
        end=Point(x=70.0, y=20.0),
        target_id="RIV_11",
        outcome=Outcome.SUCCESS,
        ball_speed_ms=17.5,
        ball_height_m=0.4,
        pressure=0.35,
        tags=["progressive"],
        frame_ref=120,
    )


def workload_state() -> WorkloadState:
    return WorkloadState(
        t_ms=60_000,
        player_id="RIV_02",
        distance_m=140.0,
        hsr_m=22.0,
        sprints=1,
        recent_load=0.4,
        fatigue=12.5,
        status=PhysicalStatus.FIT,
    )


def prob_range() -> ProbRange:
    return ProbRange(median=0.61, low=0.52, high=0.69)


def key_moment() -> KeyMoment:
    return KeyMoment(
        moment_id="km_01",
        t_ms=4_980_000,
        type=MomentType.AERIAL_DUEL,
        team_id="RIV",
        players=["RIV_05", "HIL_09"],
        frame_range=FrameRange(start=49_750, end=49_830),
        event_id="ev_004500",
        importance=0.9,
        title="Late aerial duel at the back post",
    )


def option_set() -> OptionSet:
    opt = Option(
        option_id="opt_1",
        action=ActionKind.PASS,
        target_id="RIV_11",
        target=Point(x=70.0, y=20.0),
        p_success=0.62,
        range=prob_range(),
        xt_gain=0.04,
        path=[Point(x=52.0, y=34.2), Point(x=70.0, y=20.0)],
        chosen=True,
    )
    return OptionSet(
        moment_id="km_01", t_ms=4_980_000, actor_id="RIV_08", options=[opt], best_option_id="opt_1"
    )


def what_if() -> WhatIf:
    return WhatIf(
        moment_id="km_01",
        actor_id="RIV_05",
        actual=Scenario(
            profile=ProfileRef(kind=ProfileKind.ACTUAL, player_id="RIV_05", label="Varga (tired)"),
            p_success=0.23,
            range=ProbRange(median=0.23, low=0.17, high=0.30),
        ),
        counterfactual=Scenario(
            profile=ProfileRef(
                kind=ProfileKind.ARCHETYPE, archetype=Archetype.AERIAL_CB, label="Fresh aerial CB"
            ),
            p_success=0.61,
            range=prob_range(),
        ),
        drivers=[Driver(factor="jump_reach", delta=12, unit="cm", text="+12 cm reach")],
        ghost_path=[Point(x=8.0, y=40.0), Point(x=5.5, y=42.0)],
    )


def overlay() -> Overlay:
    return Overlay(
        overlay_id="ov_km_01_whatif",
        t_ms=4_980_000,
        kind=OverlayKind.WHAT_IF,
        moment_id="km_01",
        payload={"before": 0.23, "after": 0.61},
        text={Persona.FAN: {"en": "A fresh centre-back is much more likely to win that header."}},
        grounded=True,
        source="narrator",
    )


ALL = [
    match_meta,
    player_profile,
    tracking_frame,
    event,
    workload_state,
    key_moment,
    option_set,
    what_if,
    overlay,
]
