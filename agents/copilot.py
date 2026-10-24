"""Match copilot: the chat under the live board, served over AG-UI for CopilotKit.

One Agent Framework agent with engine tools. Every number in an answer comes from a tool; the
model only chooses which tool to call and explains the result. The marking tool is where the
answers become dynamic: it re-scores every candidate against the attacker with live fatigue,
who is on the pitch, the attacker's type and side, so the same question gets a different answer
at 20' and at 80', or for a winger instead of a target man.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import HTTPException, Request
from pydantic import Field

from agents.backend import AgentFrameworkBackend
from agents.templates import decision_analyst
from mcp_server.context import EngineContext
from service.settings import Settings

INSTRUCTIONS = """You are the Decision Lens match copilot for a fully synthetic football match
between Riverside FC and Hillton United, watched live. No player is real.

Rules:
- Every number you write must come from a tool result in this conversation, quoted as given
  (probabilities as whole percentages). Never estimate or invent numbers; say it in words.
- Resolve names with find_player when unsure. Use player_stats for a player's numbers,
  player_decisions for their key decisions, match_state for the score and team numbers.
- "Who should mark X?" -> call best_marker(X). The board draws the ranking as a chart, so name
  the top pick and the runner-up and explain WHY from the tool's reasons, weights, channel,
  foot and positions (e.g. taller with more reach against a target man, quicker against a
  winger, left-footed for the left side, has played full back).
- Follow-ups such as "he's already marking Y" or "not him": call best_marker again with every
  ruled-out player in `exclude`, and say who is next and why.
- If the context says the viewer is a fan, use plain words and at most two numbers.
- Write like a pundit. Start with the answer itself, with no label such as "Verdict:". Never
  put numbers in quote marks, never name tools, lists or fields, never say where a number
  came from. Write numbers naturally, e.g. "Varga (65%)", "75 passes", "fatigue 94".
- Keep answers short: one opening sentence, then up to four bullets. British English.

Example: Varga is the man for Morrow (65%).
- Wins the high balls: he's taller with more reach, and Morrow is a target man.
- Fresh legs and better in the tackle (+14).
- Next best: Ellery (59%), strong in the air but weaker on the ground."""

LIMIT_PER_HOUR = 40  # questions per viewer
GLOBAL_PER_HOUR = 600  # questions across everyone: bounds the model spend
MAX_BODY_BYTES = 256 * 1024  # the chat resends its history; a huge one would be costly


def client_address(request: Request) -> str:
    """The caller's address. Behind Azure Container Apps the socket peer is the ingress proxy,
    which appends the real client to X-Forwarded-For; the last entry is the one it added (earlier
    entries can be forged by the caller)."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd.strip():
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "anon"


class RateLimit:
    """Model calls happen when someone asks, so cap them per caller and overall (in memory, per
    replica; the app runs a single replica)."""

    def __init__(self, per_hour: int = LIMIT_PER_HOUR, total: int = GLOBAL_PER_HOUR) -> None:
        self.per_hour = per_hour
        self.total = total
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.all: deque[float] = deque()

    @staticmethod
    def _trim(q: deque[float], now: float) -> None:
        while q and now - q[0] > 3600:
            q.popleft()

    async def __call__(self, request: Request) -> None:
        size = request.headers.get("content-length", "")
        if size.isdigit() and int(size) > MAX_BODY_BYTES:
            raise HTTPException(413, "Conversation too long; start a new chat.")
        now = time.monotonic()
        self._trim(self.all, now)
        if len(self.all) >= self.total:
            raise HTTPException(429, "The copilot is busy this hour; try again later.")
        who = client_address(request)
        q = self.hits[who]
        self._trim(q, now)
        if len(q) >= self.per_hour:
            raise HTTPException(429, "Copilot limit reached for this hour; try again later.")
        q.append(now)
        self.all.append(now)
        if len(self.hits) > 5000:  # forget callers with no recent questions
            for k in [k for k, v in self.hits.items() if not v or now - v[-1] > 3600]:
                del self.hits[k]


def viewer_scope(request: Request) -> str:
    """Whose chat threads these are: the board's random per-browser id (no sign-in on a public
    demo), else the caller's address. Viewers never see each other's threads."""
    vid = request.headers.get("x-viewer-id", "").strip()
    if vid and len(vid) <= 64 and vid.replace("-", "").isalnum():
        return f"viewer:{vid}"
    return f"addr:{client_address(request)}"


def _resolve(ctx: EngineContext, query: str) -> str:
    """A player id from an id, a full name, a surname or a shirt number."""
    q = query.strip().lower()
    if query.upper() in ctx.players:
        return query.upper()
    exact = [p for p in ctx.players.values() if p.name.lower() == q]
    if exact:
        return exact[0].player_id
    part = [p for p in ctx.players.values() if q and q in p.name.lower()]
    if len(part) == 1:
        return part[0].player_id
    raise ValueError(f"no single player matches {query!r}; use find_player")


def build_tools(get_ctx: Callable[[], EngineContext]) -> list[Any]:
    from agent_framework import tool

    def card(pid: str) -> dict[str, Any]:
        ctx = get_ctx()
        p = ctx.players[pid]
        return {
            "id": pid,
            "name": p.name,
            "team": ctx.teams[p.team_id],
            "position": p.position.value,
            "other_positions": [x.value for x in p.positions],
            "foot": p.foot.value,
            "type": p.archetype.value.replace("_", " "),
            "height_cm": round(p.physical.height_cm),
            "top_speed_ms": round(p.physical.max_speed_ms, 1),
        }

    @tool(description="Find players by name, surname or shirt number (both squads, incl. bench).")
    def find_player(
        query: Annotated[str, Field(description="name, surname or number")],
    ) -> list[dict[str, Any]]:
        ctx = get_ctx()
        q = query.strip().lower()
        on = set(ctx.pipeline.state.on_ids)
        hits = [
            p
            for p in ctx.players.values()
            if q in p.name.lower() or q == str(p.shirt_number) or q == p.player_id.lower()
        ]
        return [card(p.player_id) | {"on_pitch": p.player_id in on} for p in hits[:8]]

    @tool(
        description=(
            "A player's numbers so far: km, fatigue, sprints, passes, shots, goals, "
            "tackles, aerials."
        )
    )
    def player_stats(player: Annotated[str, Field(description="name or id")]) -> dict[str, Any]:
        pid = _resolve(get_ctx(), player)
        s = get_ctx().pipeline.player_stats(pid)
        return card(pid) | s.model_dump(mode="json", exclude={"player_id", "t_ms"})

    @tool(
        description=(
            "The decisions that cost this player most in goal odds so far, and their best one."
        )
    )
    def player_decisions(player: Annotated[str, Field(description="name or id")]) -> list[str]:
        ctx = get_ctx()
        pid = _resolve(ctx, player)
        return [decision_analyst(ctx.decision_facts(d)) for d in ctx.pipeline.player_decisions(pid)]

    @tool(
        description=(
            "Rank who should mark an opponent right now (on the pitch or a fresh sub), scored by "
            "the engine's duel models with live fatigue. Pass already-busy or ruled-out players "
            "in exclude."
        )
    )
    def best_marker(
        attacker: Annotated[str, Field(description="the opponent to mark: name or id")],
        exclude: Annotated[list[str] | None, Field(description="players ruled out")] = None,
    ) -> dict[str, Any]:
        ctx = get_ctx()
        try:
            aid = _resolve(ctx, attacker)
            skip = [_resolve(ctx, x) for x in exclude or []]
            adv = ctx.pipeline.marking_advice(aid, skip)
        except (ValueError, KeyError) as exc:  # tell the model what to fix, don't just fail
            on = set(ctx.pipeline.state.on_ids)
            return {
                "error": str(exc),
                "hint": "attacker must be an opponent on the pitch; exclude lists markers",
                "on_pitch": sorted(ctx.name(p) for p in on),
            }
        out = adv.model_dump(mode="json")
        out["attacker"] = card(aid)
        for o in out["options"]:
            o.update({k: v for k, v in card(o["player_id"]).items() if k != "id"})
            for k in ("score", "aerial", "ground", "race"):
                o[f"{k}_pct"] = round(o[k] * 100)
        out["excluded_names"] = [ctx.name(x) for x in skip]
        out["minute"] = adv.t_ms // 60_000 + 1
        return out

    @tool(description="Score, minute and team numbers (possession, shots, xG) right now.")
    def match_state() -> dict[str, Any]:
        return get_ctx().match_state()

    return [find_player, player_stats, player_decisions, best_marker, match_state]


def build_copilot(get_ctx: Callable[[], EngineContext], settings: Settings, mcp_url: str) -> Any:
    """The AG-UI wrapped agent, or None when no model is configured."""
    from agent_framework import Agent
    from agent_framework_ag_ui import AgentFrameworkAgent

    backend = AgentFrameworkBackend(settings, mcp_url)
    model = settings.azure_openai_deployment_mini
    agent = Agent(
        backend._client(model),
        INSTRUCTIONS,
        name="decision_lens_copilot",
        tools=build_tools(get_ctx),
        default_options={**backend._options(model), "max_tokens": 900},
    )
    return AgentFrameworkAgent(
        agent=agent,
        name="decision_lens_copilot",
        description="Answers questions about the live match from the engine",
        require_confirmation=False,
    )
