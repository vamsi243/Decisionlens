"""The Decision Lens MCP server: six engine tools for the agents (official MCP Python SDK, v2).

| Tool                | Returns                                                         |
| ------------------- | --------------------------------------------------------------- |
| get_match_state     | clock, score, team stats, most fatigued players                  |
| get_player_workload | distance, high-speed running, sprints, fatigue, modifiers        |
| get_options         | the option map at a key moment (or a note that there is none)    |
| what_if_swap        | swap the actor for a fresh sub / archetype / custom profile      |
| get_intensity       | intensity index per 5-minute window                               |
| get_recap_facts     | score, goals, turning points, workload leaders, intense spells    |
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.mcpserver import MCPServer

from mcp_server.context import EngineContext, SwapMode

INSTRUCTIONS = (
    "Decision Lens engine tools for a synthetic football match (Riverside FC vs Hillton United). "
    "Every number comes from the engine: quote tool results, never estimate."
)


def build_server(ctx: EngineContext) -> MCPServer:
    mcp: MCPServer = MCPServer(name="decision-lens", instructions=INSTRUCTIONS, version="0.6.0")

    @mcp.tool()
    def get_match_state() -> dict[str, Any]:
        """Current clock, score, possession, passing, shots, xG and the most fatigued players."""
        return ctx.match_state()

    @mcp.tool()
    def get_player_workload(player_id: str) -> dict[str, Any]:
        """Distance, high-speed running, sprints, fatigue (0-100), status and speed modifiers."""
        return ctx.workload(player_id).model_dump(mode="json")

    @mcp.tool()
    def get_options(moment_id: str) -> dict[str, Any]:
        """Up to four options the player on the ball had at a key moment, with success chances."""
        o = ctx.options(moment_id)
        if o is None:
            return {"moment_id": moment_id, "options": [], "note": "no on-ball decision here"}
        return o.model_dump(mode="json")

    @mcp.tool()
    async def what_if_swap(
        moment_id: str,
        mode: SwapMode = "fresh_sub",
        bench_player_id: str | None = None,
        archetype: str | None = None,
        overrides: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Re-run the moment with a different player in the actor's place.

        mode: "fresh_sub" (optionally pick bench_player_id), "archetype" (e.g. "aerial_cb",
        "overlapping_fb", "deep_playmaker", "target_man") or "custom" (overrides such as
        {"jump_reach_cm": 280, "max_speed_ms": 9.5, "reaction_s": 0.2, "passing": 85}).
        Returns before/after success probabilities with 10th-90th percentile ranges and the
        attribute differences (drivers) that explain the change.
        """
        w = await asyncio.to_thread(
            ctx.what_if_swap,
            moment_id,
            mode,
            bench_player_id=bench_player_id,
            archetype=archetype,
            overrides=overrides,
        )
        return w.model_dump(mode="json")

    @mcp.tool()
    def get_intensity() -> list[dict[str, Any]]:
        """Match intensity (0-100) for each 5-minute window so far."""
        return ctx.intensity()

    @mcp.tool()
    def get_recap_facts(until_ms: int | None = None) -> dict[str, Any]:
        """Facts for a recap: score, goals, turning points with what-ifs, workload leaders."""
        return ctx.recap_facts(until_ms)

    return mcp
