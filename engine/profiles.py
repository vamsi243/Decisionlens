"""Archetype base profiles and helpers to turn profiles + fatigue into Kinematics."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from contracts import Archetype, Modifiers, Physical, PlayerProfile, Position, Skill
from engine.physics import Kinematics

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

ARCHETYPE_LABEL = {
    Archetype.GOALKEEPER: "goalkeeper",
    Archetype.AERIAL_CB: "aerial centre-back",
    Archetype.BALL_PLAYING_CB: "ball-playing centre-back",
    Archetype.OVERLAPPING_FB: "overlapping full-back",
    Archetype.DEEP_PLAYMAKER: "deep playmaker",
    Archetype.BOX_TO_BOX: "box-to-box midfielder",
    Archetype.PRESSING_FORWARD: "pressing forward",
    Archetype.TARGET_MAN: "target man",
    Archetype.WINGER: "winger",
}

ARCHETYPE_POSITION = {
    Archetype.GOALKEEPER: Position.GK,
    Archetype.AERIAL_CB: Position.CB,
    Archetype.BALL_PLAYING_CB: Position.CB,
    Archetype.OVERLAPPING_FB: Position.FB,
    Archetype.DEEP_PLAYMAKER: Position.DM,
    Archetype.BOX_TO_BOX: Position.CM,
    Archetype.PRESSING_FORWARD: Position.ST,
    Archetype.TARGET_MAN: Position.ST,
    Archetype.WINGER: Position.W,
}


def archetype_profile(archetype: Archetype, player_id: str, team_id: str) -> PlayerProfile:
    """A textbook player of the given archetype (no jitter), standing in for `player_id`."""
    b = ARCHETYPE_BASE[archetype]
    return PlayerProfile(
        player_id=player_id,
        team_id=team_id,
        name=f"Typical {ARCHETYPE_LABEL[archetype]}",
        shirt_number=99,
        position=ARCHETYPE_POSITION[archetype],
        archetype=archetype,
        starter=False,
        physical=Physical(
            height_cm=b[0], max_speed_ms=b[1], accel_ms2=b[2], reaction_s=b[3], jump_reach_cm=b[4]
        ),
        skill=Skill(passing=b[5], aerial=b[6], tackle=b[7], finishing=b[8]),
    )


def kinematics(
    profiles: Sequence[PlayerProfile],
    pos: np.ndarray,
    vel: np.ndarray,
    modifiers: Sequence[Modifiers] | None = None,
) -> Kinematics:
    mods = modifiers or [Modifiers() for _ in profiles]
    return Kinematics(
        pos=np.asarray(pos, float).reshape(-1, 2),
        vel=np.asarray(vel, float).reshape(-1, 2),
        vmax=np.array(
            [p.physical.max_speed_ms * m.speed for p, m in zip(profiles, mods, strict=True)]
        ),
        accel=np.array(
            [p.physical.accel_ms2 * m.accel for p, m in zip(profiles, mods, strict=True)]
        ),
        reaction=np.array(
            [p.physical.reaction_s * m.reaction for p, m in zip(profiles, mods, strict=True)]
        ),
    )


def effective_reach_cm(profile: PlayerProfile, mod: Modifiers) -> float:
    """Header contact height (cm); tired legs (lower accel modifier) jump less high."""
    return profile.physical.jump_reach_cm * (0.88 + 0.12 * mod.accel)
