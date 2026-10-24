"""Orchestrator: runs the router's steps for each trigger and publishes grounded overlay cards.

Per step: response cache -> model call (timeout) -> grounding check -> one retry (the fallback
deployment after an error, or the same model told which numbers were not in the facts) ->
engine template. Agents share state through the StateStore and the MCP tools, never by passing
numbers to each other: the What-if agent picks a swap by calling `what_if_swap`, and the
Narrator reads the resulting engine numbers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from opentelemetry import trace

from agents import prompts, templates
from agents.backend import ChatBackend
from agents.cache import ResponseCache
from agents.facts import moment_facts
from agents.grounding import check, numbers_in
from agents.router import Step, Trigger, route, trigger_for
from contracts import Event, Overlay, OverlayKind, Persona
from contracts.stream import MomentAnalysis, StreamMessageType
from mcp_server.context import EngineContext
from service.ports import Publisher, StateStore
from service.settings import Settings

log = logging.getLogger("decision_lens.agents")
tracer = trace.get_tracer("decision_lens.agents")

Job = Callable[[], Awaitable[None]]


@dataclass
class StepRecord:
    step: str
    agent: str
    source: str  # agent | cache | template | engine | skipped
    ms: int
    retries: int = 0


@dataclass
class Trace:
    """One record per trigger: which steps ran and where each text came from."""

    trigger: str
    target: str
    steps: list[StepRecord] = field(default_factory=list)


class Orchestrator:
    def __init__(
        self,
        ctx: EngineContext,
        store: StateStore,
        publisher: Publisher,
        backend: ChatBackend | None,
        settings: Settings,
        cache: ResponseCache | None = None,
    ) -> None:
        self.ctx = ctx
        self.store = store
        self.publisher = publisher
        self.backend = backend
        self.settings = settings
        self.cache = cache or ResponseCache(None)
        self.timeout = settings.agent_timeout_s
        self.match_id = ctx.pipeline.meta.match_id
        self.queue: asyncio.Queue[Job] = asyncio.Queue()
        self.traces: list[Trace] = []
        self._queued: set[str] = set()
        self.swap_args: dict[str, dict[str, Any]] = {}
        # Player panel: agent lines per decision id, written at half-time and full-time.
        self.decision_lines: dict[str, dict[Persona, dict[str, str]]] = {}

    # ------------------------------------------------------------------ queueing
    def submit_moment(self, a: MomentAnalysis) -> None:
        oid = f"ov_{a.moment.moment_id}"
        if oid in self._queued:
            return
        self._queued.add(oid)
        self.queue.put_nowait(lambda: self._publish(self.moment(a)))

    def submit_period_end(self, e: Event) -> None:
        trig = Trigger.HALF_TIME if e.period.value == "1H" else Trigger.FULL_TIME
        oid = f"ov_recap_{trig.value}"
        if oid in self._queued:
            return
        self._queued.add(oid)
        self.queue.put_nowait(lambda: self._publish(self.recap(trig, e.t_ms)))
        self.queue.put_nowait(lambda: self.decision_notes(trig, e.t_ms))

    async def _publish(self, coro: Awaitable[Overlay]) -> None:
        ov = await coro
        self.store.put_overlay(ov)
        await self.publisher.publish(StreamMessageType.OVERLAY, ov)

    async def worker(self) -> None:
        while True:
            job = await self.queue.get()
            try:
                await job()
            except Exception:
                log.exception("orchestrator job failed")
            finally:
                self.queue.task_done()

    # ------------------------------------------------------------------ one model step
    async def _ask(
        self,
        trace_: Trace,
        step: Step,
        agent: str,
        instructions: str,
        facts: dict[str, Any],
        *,
        model: str,
        cache_id: str,
        use_tools: bool = False,
        max_words: int | None = None,
        numbers: bool = True,
        whole: bool = True,
    ) -> str | None:
        """One agent step, traced: a child span of the trigger's span in App Insights."""
        with tracer.start_as_current_span(f"agent.{agent}") as span:
            span.set_attribute("decision_lens.step", step.value)
            span.set_attribute("gen_ai.request.model", model)
            text = await self._ask_inner(
                trace_,
                step,
                agent,
                instructions,
                facts,
                model=model,
                cache_id=cache_id,
                use_tools=use_tools,
                max_words=max_words,
                numbers=numbers,
                whole=whole,
            )
            last = trace_.steps[-1] if trace_.steps else None
            if last is not None:
                span.set_attribute("decision_lens.source", last.source)
                span.set_attribute("decision_lens.retries", last.retries)
            return text

    async def _ask_inner(
        self,
        trace: Trace,
        step: Step,
        agent: str,
        instructions: str,
        facts: dict[str, Any],
        *,
        model: str,
        cache_id: str,
        use_tools: bool = False,
        max_words: int | None = None,
        numbers: bool = True,
        whole: bool = True,
    ) -> str | None:
        t0 = time.perf_counter()

        def usable(text: str) -> bool:
            # grounded, short enough for a card, and number-free where the reader wants words
            short = max_words is None or len(text.split()) <= max_words
            grounded = not whole or check(text, facts).ok  # else the caller checks each part
            return grounded and short and (numbers or not numbers_in(text))

        key = ResponseCache.key(self.match_id, cache_id, agent, model, prompts.PROMPT_VERSION)
        hit = self.cache.get(key)
        if hit is not None and (use_tools or usable(hit)):
            trace.steps.append(StepRecord(step, agent, "cache", self._ms(t0)))
            return hit
        if self.backend is None:
            trace.steps.append(StepRecord(step, agent, "template", self._ms(t0)))
            return None
        prompt = "FACTS:\n" + json.dumps(facts, ensure_ascii=False)
        failed = False
        for attempt in range(2):
            use_model = self.settings.azure_openai_deployment_fallback if failed else model
            try:
                text = await asyncio.wait_for(
                    self.backend.run(
                        agent, instructions, prompt, model=use_model, use_tools=use_tools
                    ),
                    self.timeout,
                )
            except Exception as exc:  # timeout, HTTP error, content filter ...
                log.warning("%s attempt %d failed: %s", agent, attempt + 1, exc)
                failed = True
                continue
            text = (text or "").strip()
            g = check(text, facts)
            if text and usable(text):
                self.cache.put(key, text)
                trace.steps.append(StepRecord(step, agent, "agent", self._ms(t0), attempt))
                return text
            log.info("%s unusable: numbers %s, %d words", agent, g.offending, len(text.split()))
            failed = False
            prompt += (
                "\n\nYour previous answer used numbers that are not in the FACTS: "
                + ", ".join(g.offending)
                + ". Rewrite it using only numbers that appear in the FACTS."
            )
        trace.steps.append(StepRecord(step, agent, "template", self._ms(t0), 1))
        return None

    @staticmethod
    def _ms(t0: float) -> int:
        return round((time.perf_counter() - t0) * 1000)

    # ------------------------------------------------------------------ key moments & fatigue
    async def moment(self, a: MomentAnalysis) -> Overlay:
        with tracer.start_as_current_span("trigger.moment") as span:
            span.set_attribute("decision_lens.moment_id", a.moment.moment_id)
            span.set_attribute("decision_lens.moment_type", a.moment.type.value)
            ov = await self._moment(a)
            span.set_attribute("decision_lens.card_source", ov.source)
            return ov

    async def _moment(self, a: MomentAnalysis) -> Overlay:
        m = a.moment
        mid = m.moment_id
        trig = trigger_for(m)
        trace = Trace(trig.value, mid)
        steps = route(trig)
        facts = moment_facts(self.ctx, a)
        mini = self.settings.azure_openai_deployment_mini
        nano = self.settings.azure_openai_deployment_nano
        extras: dict[str, Any] = {"route": [s.value for s in steps]}

        if Step.MOMENT in steps:
            framing = await self._ask(
                trace, Step.MOMENT, "moment", prompts.MOMENT, facts, model=mini, cache_id=mid
            )
            if framing:
                extras["framing"] = framing

        if Step.WHAT_IF in steps and trig == Trigger.KEY_MOMENT and "what_if" in facts:
            reason = await self._what_if_agent(trace, mid, facts, mini)
            updated = self.store.analysis(mid)
            if updated is not None:
                a = updated
                facts = moment_facts(self.ctx, a)
            if reason:
                extras["swap_reason"] = reason
        elif Step.WHAT_IF in steps:  # fatigue: the engine proposes same-position fresh subs
            trace.steps.append(StepRecord(Step.WHAT_IF, "engine", "engine", 0))

        narr = {**facts, **{k: v for k, v in extras.items() if k != "route"}}
        wf = facts.get("what_if")
        if wf and trig != Trigger.FATIGUE:  # the engine's words for the swing, used verbatim
            verb = templates.VERB.get(facts["type"], "to come out on top")
            narr["swing_words"] = f"{templates.swing(wf['actual_pct'], wf['swap_pct'])} {verb}"
        if trig == Trigger.FATIGUE:
            t_analyst, t_fan = templates.fatigue_analyst(facts), templates.fatigue_fan(facts)
        else:
            t_analyst, t_fan = templates.moment_analyst(facts), templates.moment_fan(facts)
        analyst = await self._ask(
            trace,
            Step.NARRATOR,
            "narrator_analyst",
            prompts.NARRATOR_ANALYST,
            narr,
            model=mini,
            cache_id=mid,
            max_words=32,
        )
        # A fatigue alert's fan line is fixed engine wording; a model adds nothing but risk.
        fan = (
            None
            if trig == Trigger.FATIGUE
            else await self._ask(
                trace,
                Step.NARRATOR,
                "narrator_fan",
                prompts.NARRATOR_FAN,
                narr,
                model=nano,
                cache_id=mid,
                max_words=20,
                numbers=False,
            )
        )
        self.traces.append(trace)
        kind = (
            OverlayKind.FATIGUE
            if trig == Trigger.FATIGUE
            else OverlayKind.WHAT_IF
            if a.what_if
            else OverlayKind.OPTIONS
            if a.options
            else OverlayKind.MOMENT
        )
        return self._overlay(
            f"ov_{mid}",
            m.t_ms,
            kind,
            mid,
            {**facts, **extras},
            analyst or t_analyst,
            fan or t_fan,
            trace,
        )

    async def _what_if_agent(
        self, trace: Trace, mid: str, facts: dict[str, Any], model: str
    ) -> str | None:
        """Let the agent choose a swap through the MCP tool; replay a cached choice locally."""
        key = ResponseCache.key(self.match_id, mid, "what_if", model, prompts.PROMPT_VERSION)
        cached = self.cache.get(key)
        if cached is not None:
            choice = json.loads(cached)
            try:
                await asyncio.to_thread(self.ctx.what_if_swap, mid, **choice["args"])
                trace.steps.append(StepRecord(Step.WHAT_IF, "what_if", "cache", 0))
                return str(choice.get("reason") or "") or None
            except ValueError:
                pass
        if self.backend is None:
            trace.steps.append(StepRecord(Step.WHAT_IF, "what_if", "engine", 0))
            return None
        bench = self.ctx.bench(mid)
        wf = {**facts, "bench": bench}
        before = len(self.ctx.swap_log)
        reason = await self._ask(
            trace,
            Step.WHAT_IF,
            "what_if",
            prompts.WHAT_IF,
            wf,
            model=model,
            cache_id=f"{mid}#reason",
            use_tools=True,
        )
        if len(self.ctx.swap_log) > before:
            args = self.ctx.swap_log[-1]
            self.cache.put(key, json.dumps({"args": args, "reason": reason or ""}))
        return reason

    # ------------------------------------------------------------------ recaps
    async def recap(self, trig: Trigger, t_ms: int, ctx: EngineContext | None = None) -> Overlay:
        """Half-time / full-time recap; `ctx` lets the recap page ask about the final whistle."""
        with tracer.start_as_current_span(f"trigger.{trig.value}") as span:
            ov = await self._recap(trig, t_ms, ctx or self.ctx)
            span.set_attribute("decision_lens.card_source", ov.source)
            return ov

    async def _recap(self, trig: Trigger, t_ms: int, ctx: EngineContext) -> Overlay:
        trace = Trace(trig.value, f"recap_{trig.value}")
        mini = self.settings.azure_openai_deployment_mini
        nano = self.settings.azure_openai_deployment_nano
        cid = f"recap_{trig.value}"
        state = ctx.match_state()
        summary = await self._ask(
            trace,
            Step.INTERPRETER,
            "interpreter",
            prompts.INTERPRETER,
            state,
            model=mini,
            cache_id=cid,
        )
        facts = ctx.recap_facts(t_ms)
        rf = {**facts, **({"state_summary": summary} if summary else {})}
        analyst = await self._ask(
            trace,
            Step.RECAP,
            "recap_analyst",
            prompts.RECAP_ANALYST,
            rf,
            model=mini,
            cache_id=cid,
            max_words=48,
        )
        fan = await self._ask(
            trace,
            Step.RECAP,
            "recap_fan",
            prompts.RECAP_FAN,
            rf,
            model=nano,
            cache_id=cid,
            max_words=36,
        )
        self.traces.append(trace)
        return self._overlay(
            f"ov_recap_{trig.value}",
            t_ms,
            OverlayKind.RECAP,
            None,
            {
                **rf,
                "title": "Half-time recap" if trig == Trigger.HALF_TIME else "Full-time recap",
                "minute": round(t_ms / 60_000),
            },
            analyst or templates.recap_analyst(facts),
            fan or templates.recap_fan(facts),
            trace,
        )

    # ------------------------------------------------------------------ player decisions
    async def decision_notes(self, trig: Trigger, t_ms: int) -> None:
        """One call per team: a short line for every player's engine-ranked decisions so far.
        Lines that are ungrounded, too long, or (for fans) contain numbers are dropped, and the
        panel keeps the template for those."""
        pipe = self.ctx.pipeline
        for team in pipe.meta.teams:
            ids = [p.player_id for p in pipe.players if p.team_id == team.team_id]
            facts: list[dict[str, Any]] = []
            for pid in ids:
                for d in await asyncio.to_thread(pipe.player_decisions, pid, t_ms):
                    facts.append(self.ctx.decision_facts(d))
            if not facts:
                continue
            trace = Trace(trig.value, f"decisions_{trig.value}_{team.team_id}")
            raw = await self._ask(
                trace,
                Step.DECISIONS,
                "decisions",
                prompts.DECISIONS,
                {"team": team.name, "decisions": facts},
                model=self.settings.azure_openai_deployment_mini,
                cache_id=f"decisions_{trig.value}_{team.team_id}",
                whole=False,  # one bad line shouldn't sink the rest: each is checked on its own
            )
            self.traces.append(trace)
            self.decision_lines.update(_decision_lines(raw, facts))

    # ------------------------------------------------------------------ overlay
    def _overlay(
        self,
        oid: str,
        t_ms: int,
        kind: OverlayKind,
        moment_id: str | None,
        payload: dict[str, Any],
        analyst: str,
        fan: str,
        trace: Trace,
    ) -> Overlay:
        narr = [s.source for s in trace.steps if s.step in (Step.NARRATOR, Step.RECAP)]
        source = (
            "agents"
            if narr and all(s in ("agent", "cache") for s in narr)
            else "template"
            if all(s == "template" for s in narr)
            else "mixed"
        )
        payload = {**payload, "trace": [s.__dict__ for s in trace.steps]}
        return Overlay(
            overlay_id=oid,
            t_ms=t_ms,
            show_for_ms=12_000 if kind == OverlayKind.RECAP else 9_000,
            kind=kind,
            moment_id=moment_id,
            payload=payload,
            text={Persona.ANALYST: {"en": analyst}, Persona.FAN: {"en": fan}},
            grounded=True,  # agent text passed the check; templates are built from the facts
            source=source,
        )


def _decision_lines(
    raw: str | None, facts: list[dict[str, Any]]
) -> dict[str, dict[Persona, dict[str, str]]]:
    """Parse the Decisions agent's JSON and keep only lines that pass the card checks."""
    if not raw:
        return {}
    body = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(body)
    except ValueError:
        log.info("decisions: reply was not JSON")
        return {}
    by_id = {f["id"]: f for f in facts}
    out: dict[str, dict[Persona, dict[str, str]]] = {}
    for did, lines in parsed.items() if isinstance(parsed, dict) else []:
        f = by_id.get(did)
        if f is None or not isinstance(lines, dict):
            continue
        analyst, fan = str(lines.get("analyst", "")).strip(), str(lines.get("fan", "")).strip()
        ok = (
            analyst
            and fan
            and check(analyst, f).ok
            and len(analyst.split()) <= 30
            and len(fan.split()) <= 20
            and not numbers_in(fan)
        )
        if ok:
            out[did] = {Persona.ANALYST: {"en": analyst}, Persona.FAN: {"en": fan}}
    return out
