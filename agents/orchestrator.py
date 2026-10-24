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

from agents import prompts, templates
from agents.backend import ChatBackend
from agents.cache import ResponseCache
from agents.facts import moment_facts
from agents.grounding import check
from agents.router import Step, Trigger, route, trigger_for
from contracts import Event, Overlay, OverlayKind, Persona
from contracts.stream import MomentAnalysis, StreamMessageType
from mcp_server.context import EngineContext
from service.ports import Publisher, StateStore
from service.settings import Settings

log = logging.getLogger("decision_lens.agents")

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
        trace: Trace,
        step: Step,
        agent: str,
        instructions: str,
        facts: dict[str, Any],
        *,
        model: str,
        cache_id: str,
        use_tools: bool = False,
    ) -> str | None:
        t0 = time.perf_counter()
        key = ResponseCache.key(self.match_id, cache_id, agent, model, prompts.PROMPT_VERSION)
        hit = self.cache.get(key)
        if hit is not None and (use_tools or check(hit, facts).ok):
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
            if text and g.ok:
                self.cache.put(key, text)
                trace.steps.append(StepRecord(step, agent, "agent", self._ms(t0), attempt))
                return text
            log.info("%s ungrounded numbers %s", agent, g.offending)
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
        )
        fan = await self._ask(
            trace,
            Step.NARRATOR,
            "narrator_fan",
            prompts.NARRATOR_FAN,
            narr,
            model=nano,
            cache_id=mid,
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
    async def recap(self, trig: Trigger, t_ms: int) -> Overlay:
        trace = Trace(trig.value, f"recap_{trig.value}")
        mini = self.settings.azure_openai_deployment_mini
        nano = self.settings.azure_openai_deployment_nano
        cid = f"recap_{trig.value}"
        state = self.ctx.match_state()
        summary = await self._ask(
            trace,
            Step.INTERPRETER,
            "interpreter",
            prompts.INTERPRETER,
            state,
            model=mini,
            cache_id=cid,
        )
        facts = self.ctx.recap_facts(t_ms)
        rf = {**facts, **({"state_summary": summary} if summary else {})}
        analyst = await self._ask(
            trace,
            Step.RECAP,
            "recap_analyst",
            prompts.RECAP_ANALYST,
            rf,
            model=mini,
            cache_id=cid,
        )
        fan = await self._ask(
            trace, Step.RECAP, "recap_fan", prompts.RECAP_FAN, rf, model=nano, cache_id=cid
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
