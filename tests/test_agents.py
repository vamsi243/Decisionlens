import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from agents.cache import ResponseCache
from agents.grounding import allowed_numbers, check, numbers_in
from agents.orchestrator import Orchestrator
from agents.router import ROUTES, Step, Trigger, route, trigger_for, uses_model
from agents.translator import Translator
from contracts import MomentType, Overlay, OverlayKind, Persona
from mcp_server.__main__ import full_time_context
from mcp_server.context import EngineContext
from mcp_server.server import build_server
from service.settings import Settings

SAMPLE = Path("data/samples/match_42")


class Pub:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def publish(self, kind: Any, data: Any) -> None:
        self.sent.append((kind, data))

    async def publish_raw(self, kind: Any, raw: bytes) -> None: ...


Responder = Callable[[str, str, str, bool], str]


class FakeBackend:
    """Stands in for Azure OpenAI: answers per agent via a function, records every call."""

    def __init__(self, respond: Responder) -> None:
        self.respond = respond
        self.calls: list[tuple[str, str]] = []

    async def run(
        self, agent: str, instructions: str, prompt: str, *, model: str, use_tools: bool = False
    ) -> str:
        self.calls.append((agent, model))
        return self.respond(agent, prompt, model, use_tools)


def facts_of(prompt: str) -> dict[str, Any]:
    body = prompt.split("FACTS:\n", 1)[1].split("\n\nYour previous answer", 1)[0]
    return json.loads(body)  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def ctx() -> EngineContext:
    return full_time_context(SAMPLE)


def settings() -> Settings:
    return Settings(_env_file=None)


def scripted(ctx: EngineContext, kind: MomentType):  # type: ignore[no-untyped-def]
    return next(
        ctx.store.analysis(m.moment_id)
        for m in ctx.store.moments()
        if m.type == kind and ctx.store.analysis(m.moment_id) is not None
    )


def numbers_ok(ov: Overlay) -> bool:
    payload = {k: v for k, v in ov.payload.items() if k != "trace"}
    return all(check(t, payload).ok for p in ov.text.values() for t in p.values())


# --- router & grounding ----------------------------------------------------------------------


def test_router_table() -> None:
    assert route(Trigger.FRAME) == (Step.ENGINE,)
    assert route(Trigger.KEY_MOMENT) == (Step.MOMENT, Step.WHAT_IF, Step.NARRATOR)
    assert route(Trigger.FATIGUE) == (Step.WHAT_IF, Step.NARRATOR)
    assert route(Trigger.LANGUAGE_CHANGE) == (Step.TRANSLATOR,)
    assert route(Trigger.FULL_TIME) == (Step.INTERPRETER, Step.RECAP)
    assert not uses_model(Trigger.FRAME) and not uses_model(Trigger.EVENT)
    assert not uses_model(Trigger.LANGUAGE_CHANGE)
    assert set(ROUTES) == set(Trigger)


def test_trigger_for(ctx: EngineContext) -> None:
    kinds = {m.type: trigger_for(m) for m in ctx.store.moments()}
    assert kinds[MomentType.FATIGUE_ALERT] == Trigger.FATIGUE
    assert kinds[MomentType.AERIAL_DUEL] == Trigger.KEY_MOMENT


def test_grounding() -> None:
    facts = {"p": 0.43, "range": [4, 5], "drivers": ["+32 cm reach"], "minute": 87}
    assert check("It went from 4% to 43%, +32 cm reach, 87th minute.", facts).ok
    assert check("0.43, or 43.0 percent", facts).ok
    bad = check("A 61% chance, 2 metres away", facts)
    assert not bad.ok and bad.offending == ("61", "2")
    assert check(chr(0x2212) + "4 and 5", facts).ok
    assert [v for _, v in numbers_in("1,5 and -3")] == [1.5, 3.0]
    assert 43 in allowed_numbers({"x": 0.43})


# --- orchestrator ----------------------------------------------------------------------------


def test_every_scripted_moment_gets_grounded_template_cards_without_a_model(
    ctx: EngineContext,
) -> None:
    orch = Orchestrator(ctx, ctx.store, Pub(), None, settings())
    for kind in (
        MomentType.LINE_BREAKING_PASS,
        MomentType.PRESS_TURNOVER,
        MomentType.BIG_CHANCE,
        MomentType.RECOVERY_RUN,
        MomentType.AERIAL_DUEL,
    ):
        a = scripted(ctx, kind)
        ov = asyncio.run(orch.moment(a))
        assert ov.source == "template" and ov.grounded
        assert ov.text[Persona.ANALYST]["en"] != ov.text[Persona.FAN]["en"]
        assert numbers_ok(ov), ov.text
        if a.what_if:  # the card's numbers are the engine's
            assert ov.payload["what_if"]["swap_pct"] == round(
                a.what_if.counterfactual.p_success * 100
            )
            assert f"{ov.payload['what_if']['actual_pct']}%" in ov.text[Persona.ANALYST]["en"]


def test_agent_text_is_used_when_grounded(ctx: EngineContext) -> None:
    def respond(agent: str, prompt: str, model: str, tools: bool) -> str:
        f = facts_of(prompt)
        if agent == "moment":
            return "A late header that could decide the match."
        if agent == "narrator_analyst":
            w = f["what_if"]
            return f"{w['player']} had {w['actual_pct']}%; {w['swap']} gets {w['swap_pct']}%."
        if agent == "narrator_fan":
            return "A fresh centre-back would have been much more likely to win it."
        return "ok"

    backend = FakeBackend(respond)
    orch = Orchestrator(ctx, ctx.store, Pub(), backend, settings())
    ov = asyncio.run(orch.moment(scripted(ctx, MomentType.AERIAL_DUEL)))
    assert ov.source == "agents"
    assert ov.payload["framing"].startswith("A late header")
    models = dict(backend.calls)
    assert models["narrator_fan"] == settings().azure_openai_deployment_nano
    assert models["narrator_analyst"] == settings().azure_openai_deployment_mini


def test_ungrounded_text_is_retried_then_falls_back(ctx: EngineContext) -> None:
    attempts: dict[str, int] = {}

    def respond(agent: str, prompt: str, model: str, tools: bool) -> str:
        attempts[agent] = attempts.get(agent, 0) + 1
        if agent == "narrator_analyst":  # fixed on the retry
            if "previous answer" in prompt:
                return f"The engine says {facts_of(prompt)['what_if']['actual_pct']}%."
            return "He had a 99% chance."
        if agent == "narrator_fan":  # never grounded: must fall back to the template
            return "Something like 77 times better."
        return "No numbers here."

    orch = Orchestrator(ctx, ctx.store, Pub(), FakeBackend(respond), settings())
    ov = asyncio.run(orch.moment(scripted(ctx, MomentType.RECOVERY_RUN)))
    assert attempts["narrator_analyst"] == 2 and attempts["narrator_fan"] == 2
    assert "99" not in ov.text[Persona.ANALYST]["en"]
    assert "77" not in ov.text[Persona.FAN]["en"]
    assert ov.source == "mixed" and numbers_ok(ov)


def test_killing_the_model_still_shows_a_card(ctx: EngineContext) -> None:
    def respond(agent: str, prompt: str, model: str, tools: bool) -> str:
        raise ConnectionError("model endpoint down")

    backend = FakeBackend(respond)
    orch = Orchestrator(ctx, ctx.store, Pub(), backend, settings())
    ov = asyncio.run(orch.moment(scripted(ctx, MomentType.BIG_CHANCE)))
    assert ov.source == "template" and numbers_ok(ov)
    # one retry on the fallback deployment after the error
    tried = [m for a, m in backend.calls if a == "narrator_analyst"]
    assert tried == [
        settings().azure_openai_deployment_mini,
        settings().azure_openai_deployment_fallback,
    ]


def test_what_if_agent_swaps_through_the_tool_and_caches_the_choice(
    ctx: EngineContext, tmp_path: Path
) -> None:
    def respond(agent: str, prompt: str, model: str, tools: bool) -> str:
        if agent == "what_if":
            assert tools
            mid = facts_of(prompt)["moment_id"]
            ctx.what_if_swap(mid, "archetype", archetype="aerial_cb")  # the MCP tool call
            return "An aerial specialist tests whether this was a mismatch."
        return "Fine."

    cache = ResponseCache(tmp_path / "cache.json")
    a = scripted(ctx, MomentType.AERIAL_DUEL)
    orch = Orchestrator(ctx, ctx.store, Pub(), FakeBackend(respond), settings(), cache)
    ov = asyncio.run(orch.moment(a))
    assert ov.payload["what_if"]["swap"] == "An aerial centre-back"
    assert ov.payload["swap_reason"].startswith("An aerial specialist")

    # a new orchestrator with no model replays the cached choice on the engine
    ctx.store.put_analysis(a)
    orch2 = Orchestrator(
        ctx, ctx.store, Pub(), None, settings(), ResponseCache(tmp_path / "cache.json")
    )
    ov2 = asyncio.run(orch2.moment(a))
    assert ov2.payload["what_if"]["swap"] == "An aerial centre-back"
    assert any(s["source"] == "cache" for s in ov2.payload["trace"])
    ctx.store.put_analysis(a)  # leave the shared store as it was


def test_recap_and_fatigue_cards(ctx: EngineContext) -> None:
    orch = Orchestrator(ctx, ctx.store, Pub(), None, settings())
    ov = asyncio.run(orch.recap(Trigger.FULL_TIME, 5_400_000))
    assert ov.kind == OverlayKind.RECAP and numbers_ok(ov)
    assert "2-2" in ov.text[Persona.ANALYST]["en"]
    fat = next(m for m in ctx.store.moments() if m.type == MomentType.FATIGUE_ALERT)
    fov = asyncio.run(orch.moment(ctx.store.analysis(fat.moment_id)))  # type: ignore[arg-type]
    assert fov.kind == OverlayKind.FATIGUE and numbers_ok(fov)
    assert fov.payload["route"] == ["what_if", "narrator"]


# --- MCP tools & translator --------------------------------------------------------------------


def test_mcp_server_exposes_the_six_tools(ctx: EngineContext) -> None:
    srv = build_server(ctx)

    async def go() -> tuple[list[str], str]:
        tools = [t.name for t in await srv.list_tools()]
        res = await srv.call_tool("get_match_state", {})
        return tools, str(res)

    tools, state = asyncio.run(go())
    assert tools == [
        "get_match_state",
        "get_player_workload",
        "get_options",
        "what_if_swap",
        "get_intensity",
        "get_recap_facts",
    ]
    assert "Riverside FC" in state


def test_translator_adds_a_language_without_a_model(ctx: EngineContext) -> None:
    seen: list[dict[str, Any]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen.append({"to": req.url.params["to"], "n": len(body)})
        return httpx.Response(
            200, json=[{"translations": [{"text": "ES: " + b["Text"]}]} for b in body]
        )

    s = settings().model_copy(update={"azure_translator_key": "test"})
    tr = Translator(s, transport=httpx.MockTransport(handler))
    orch = Orchestrator(ctx, ctx.store, Pub(), None, settings())
    ov = asyncio.run(orch.moment(scripted(ctx, MomentType.AERIAL_DUEL)))
    es = asyncio.run(tr.overlay(ov, "es"))
    assert es is not None and es.text[Persona.FAN]["es"].startswith("ES: ")
    asyncio.run(tr.overlay(ov, "es"))  # cached: no second request
    assert seen == [{"to": "es", "n": 2}]
    assert asyncio.run(Translator(settings()).overlay(ov, "es")) is None  # no key
