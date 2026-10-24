"""The rules router: a plain decision table that says what runs for each trigger.

No model decides what to run. Frames and events never touch a model; only key moments,
fatigue alerts, language changes and the two whistles do.

| Trigger              | Runs                               |
| -------------------- | ---------------------------------- |
| Every frame or event | Engine only, no model              |
| Key moment           | Moment -> What-if -> Narrator      |
| Fatigue over 80      | What-if (fresh sub) -> Narrator    |
| Language change      | Translator only                    |
| Half-time, full-time | Interpreter -> Recap               |
"""

from __future__ import annotations

from enum import StrEnum

from contracts import KeyMoment, MomentType


class Trigger(StrEnum):
    FRAME = "frame"
    EVENT = "event"
    KEY_MOMENT = "key_moment"
    FATIGUE = "fatigue"
    LANGUAGE_CHANGE = "language_change"
    HALF_TIME = "half_time"
    FULL_TIME = "full_time"


class Step(StrEnum):
    ENGINE = "engine"
    MOMENT = "moment"
    WHAT_IF = "what_if"
    NARRATOR = "narrator"
    TRANSLATOR = "translator"
    INTERPRETER = "interpreter"
    RECAP = "recap"


ROUTES: dict[Trigger, tuple[Step, ...]] = {
    Trigger.FRAME: (Step.ENGINE,),
    Trigger.EVENT: (Step.ENGINE,),
    Trigger.KEY_MOMENT: (Step.MOMENT, Step.WHAT_IF, Step.NARRATOR),
    Trigger.FATIGUE: (Step.WHAT_IF, Step.NARRATOR),
    Trigger.LANGUAGE_CHANGE: (Step.TRANSLATOR,),
    Trigger.HALF_TIME: (Step.INTERPRETER, Step.RECAP),
    Trigger.FULL_TIME: (Step.INTERPRETER, Step.RECAP),
}

MODEL_STEPS = {Step.MOMENT, Step.WHAT_IF, Step.NARRATOR, Step.INTERPRETER, Step.RECAP}


def route(trigger: Trigger) -> tuple[Step, ...]:
    return ROUTES[trigger]


def uses_model(trigger: Trigger) -> bool:
    return any(s in MODEL_STEPS for s in ROUTES[trigger])


def trigger_for(moment: KeyMoment) -> Trigger:
    return Trigger.FATIGUE if moment.type == MomentType.FATIGUE_ALERT else Trigger.KEY_MOMENT
