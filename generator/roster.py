"""Invented rosters, formations and archetype profiles for Riverside FC and Hillton United.

Every name here is invented. Formation slots are team-relative: `fx` metres from the team's own
goal line, `fy` across the pitch as seen by that team (the away team is mirrored on both axes).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from contracts import (
    Archetype,
    MatchMeta,
    Physical,
    PlayerProfile,
    Position,
    Skill,
    TeamColours,
    TeamMeta,
)

HOME, AWAY = 0, 1
TEAM_IDS = ("RIV", "HIL")

FORMATIONS: dict[str, dict[str, tuple[float, float]]] = {
    "4-3-3": {
        "GK": (4, 34),
        "RB": (20, 10),
        "RCB": (17, 26),
        "LCB": (17, 42),
        "LB": (20, 58),
        "DM": (30, 34),
        "RCM": (40, 22),
        "LCM": (40, 46),
        "RW": (55, 9),
        "ST": (58, 34),
        "LW": (55, 59),
    },
    "4-2-3-1": {
        "GK": (4, 34),
        "RB": (20, 10),
        "RCB": (17, 26),
        "LCB": (17, 42),
        "LB": (20, 58),
        "RDM": (31, 27),
        "LDM": (31, 41),
        "RW": (50, 11),
        "AM": (50, 34),
        "LW": (50, 57),
        "ST": (59, 34),
    },
}

# height_cm, max_speed_ms, accel_ms2, reaction_s, jump_reach_cm, passing, aerial, tackle, finishing
ARCHETYPE_BASE: dict[Archetype, tuple[float, ...]] = {
    Archetype.GOALKEEPER: (190, 7.4, 3.0, 0.22, 250, 58, 72, 30, 10),
    Archetype.AERIAL_CB: (193, 8.3, 3.2, 0.26, 270, 58, 88, 80, 30),
    Archetype.BALL_PLAYING_CB: (185, 8.6, 3.5, 0.24, 255, 80, 70, 75, 30),
    Archetype.OVERLAPPING_FB: (177, 9.4, 4.2, 0.23, 240, 70, 50, 68, 35),
    Archetype.DEEP_PLAYMAKER: (180, 8.4, 3.6, 0.22, 245, 90, 55, 62, 50),
    Archetype.BOX_TO_BOX: (182, 9.0, 3.9, 0.23, 250, 76, 64, 70, 60),
    Archetype.PRESSING_FORWARD: (181, 9.3, 4.1, 0.21, 248, 70, 60, 50, 78),
    Archetype.TARGET_MAN: (194, 8.4, 3.3, 0.25, 275, 64, 90, 40, 80),
    Archetype.WINGER: (175, 9.8, 4.4, 0.21, 235, 74, 42, 40, 70),
}

POSITION_OF_SLOT = {
    "GK": Position.GK,
    "RB": Position.FB,
    "LB": Position.FB,
    "RCB": Position.CB,
    "LCB": Position.CB,
    "DM": Position.DM,
    "RDM": Position.DM,
    "LDM": Position.DM,
    "RCM": Position.CM,
    "LCM": Position.CM,
    "AM": Position.AM,
    "RW": Position.W,
    "LW": Position.W,
    "ST": Position.ST,
}


@dataclass(frozen=True)
class RosterEntry:
    shirt: int
    name: str
    archetype: Archetype
    slot: str | None  # starting slot; None for substitutes
    position: Position
    overrides: tuple[tuple[str, float], ...] = ()


def _e(
    shirt: int,
    name: str,
    arch: Archetype,
    slot: str | None,
    pos: Position | None = None,
    **over: float,
) -> RosterEntry:
    position = pos or POSITION_OF_SLOT[slot or "GK"]
    return RosterEntry(shirt, name, arch, slot, position, tuple(sorted(over.items())))


A = Archetype
ROSTERS: dict[str, list[RosterEntry]] = {
    "RIV": [
        _e(1, "Elias Marrow", A.GOALKEEPER, "GK"),
        # Jonah Pell is deliberately weak in the air: he loses the scripted back-post duel.
        _e(2, "Jonah Pell", A.OVERLAPPING_FB, "RB", height_cm=175, jump_reach_cm=232, aerial=44),
        # Kieran Holt bombs forward all game: the tired full-back of the recovery-run moment.
        _e(3, "Kieran Holt", A.OVERLAPPING_FB, "LB"),
        _e(4, "Ansel Brightwater", A.BALL_PLAYING_CB, "LCB"),
        _e(5, "Tomas Varga", A.AERIAL_CB, "RCB"),
        _e(6, "Mateo Quill", A.DEEP_PLAYMAKER, "DM"),
        _e(8, "Rafe Okonjo", A.BOX_TO_BOX, "RCM"),
        _e(10, "Luca Ferrandi", A.BOX_TO_BOX, "LCM"),
        _e(7, "Dario Venn", A.WINGER, "RW"),
        _e(9, "Callum Reyes-Ward", A.PRESSING_FORWARD, "ST"),
        _e(11, "Sami Achterberg", A.WINGER, "LW"),
        _e(12, "Owen Tarrant", A.GOALKEEPER, None, Position.GK),
        _e(14, "Felix Dunmore", A.AERIAL_CB, None, Position.CB),
        _e(15, "Nico Hallam", A.OVERLAPPING_FB, None, Position.FB),
        _e(16, "Idris Calloway", A.BOX_TO_BOX, None, Position.CM),
        _e(17, "Bram Ellery", A.TARGET_MAN, None, Position.ST),
    ],
    "HIL": [
        _e(1, "Piet Lowry", A.GOALKEEPER, "GK"),
        _e(2, "Arlo Mensforth", A.OVERLAPPING_FB, "RB"),
        _e(3, "Ravi Castellan", A.OVERLAPPING_FB, "LB"),
        _e(4, "Gideon Strand", A.AERIAL_CB, "RCB"),
        _e(5, "Milo Ravenscroft", A.BALL_PLAYING_CB, "LCB"),
        _e(6, "Yusuf Brennick", A.DEEP_PLAYMAKER, "RDM"),
        _e(8, "Teo Lindqvist", A.BOX_TO_BOX, "LDM"),
        _e(10, "Jules Faraday", A.DEEP_PLAYMAKER, "AM", Position.AM),
        _e(7, "Ezra Kollmann", A.WINGER, "RW"),
        _e(9, "Dax Morrow", A.TARGET_MAN, "ST", height_cm=195, jump_reach_cm=279, aerial=92),
        _e(11, "Noah Vantongeren", A.WINGER, "LW"),
        _e(13, "Linus Fairweather", A.GOALKEEPER, None, Position.GK),
        _e(14, "Corin Ashby", A.AERIAL_CB, None, Position.CB),
        _e(15, "Hugo Strickland", A.OVERLAPPING_FB, None, Position.FB),
        _e(16, "Matias Orrell", A.BOX_TO_BOX, None, Position.CM),
        _e(17, "Remy Okafor-Lane", A.PRESSING_FORWARD, None, Position.ST),
    ],
}

# Forward-run multipliers. Holt (RIV_03) bombs on all game so he is Riverside's most tired
# player by the 71' recovery run; Kollmann (HIL_07) saves his legs so he arrives fresher.
WORK_RATE: dict[str, float] = {"RIV_03": 1.6, "HIL_07": 0.35, "HIL_11": 0.7}

TEAM_META = {
    "RIV": dict(
        name="Riverside FC",
        formation="4-3-3",
        colours=TeamColours(primary="#1a1a1a", secondary="#ffffff"),
    ),
    "HIL": dict(
        name="Hillton United",
        formation="4-2-3-1",
        colours=TeamColours(primary="#ffffff", secondary="#1a1a1a"),
    ),
}

_LIMITS = {
    "height_cm": (150, 210),
    "max_speed_ms": (5, 11),
    "accel_ms2": (1, 8),
    "reaction_s": (0.1, 0.6),
    "jump_reach_cm": (180, 320),
}


@dataclass
class RosterPlayer:
    profile: PlayerProfile
    team: int
    slot: str | None

    @property
    def id(self) -> str:
        return self.profile.player_id


@dataclass
class Roster:
    meta: MatchMeta
    players: list[RosterPlayer]

    def formation(self, team: int) -> dict[str, tuple[float, float]]:
        return FORMATIONS[self.meta.teams[team].formation]


def _profile(rng: np.random.Generator, team_id: str, e: RosterEntry) -> PlayerProfile:
    base = ARCHETYPE_BASE[e.archetype]
    phys_jitter = 1 + rng.normal(0, 0.025, 5)
    skill_jitter = rng.normal(0, 4, 4)
    phys = dict(
        zip(
            ["height_cm", "max_speed_ms", "accel_ms2", "reaction_s", "jump_reach_cm"],
            (b * j for b, j in zip(base[:5], phys_jitter, strict=True)),
            strict=True,
        )
    )
    skill = dict(
        zip(
            ["passing", "aerial", "tackle", "finishing"],
            (b + j for b, j in zip(base[5:], skill_jitter, strict=True)),
            strict=True,
        )
    )
    for key, value in e.overrides:
        (phys if key in phys else skill)[key] = value
    for key, (lo, hi) in _LIMITS.items():
        phys[key] = round(float(np.clip(phys[key], lo, hi)), 3)
    skill = {k: round(float(np.clip(v, 0, 100)), 1) for k, v in skill.items()}
    return PlayerProfile(
        player_id=f"{team_id}_{e.shirt:02d}",
        team_id=team_id,
        name=e.name,
        shirt_number=e.shirt,
        position=e.position,
        archetype=e.archetype,
        starter=e.slot is not None,
        physical=Physical(**phys),
        skill=Skill(**skill),
    )


def build_roster(seed: int, period_length_ms: int = 45 * 60 * 1000) -> Roster:
    rng = np.random.default_rng([seed, 1])
    teams = [
        TeamMeta(team_id=tid, short_name=tid, is_home=(i == HOME), **TEAM_META[tid])
        for i, tid in enumerate(TEAM_IDS)
    ]
    meta = MatchMeta(
        match_id=f"match_{seed}", seed=seed, teams=teams, period_length_ms=period_length_ms
    )
    players = [
        RosterPlayer(profile=_profile(rng, tid, e), team=team, slot=e.slot)
        for team, tid in enumerate(TEAM_IDS)
        for e in ROSTERS[tid]
    ]
    return Roster(meta=meta, players=players)
