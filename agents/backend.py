"""Model backend: Microsoft Agent Framework agents on Azure OpenAI in Foundry.

`ChatBackend` is the seam the orchestrator talks to. `AgentFrameworkBackend` builds an
Agent Framework `Agent` per call on an `OpenAIChatClient` (Responses API) pointed at the Azure
OpenAI deployment, with the lowest reasoning effort; the What-if agent also gets the Decision Lens
MCP server as a tool. With no endpoint or key configured there is no backend and every card is
a grounded template.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Protocol

from service.settings import Settings

log = logging.getLogger("decision_lens.agents")

MCP_TOOLS = ("what_if_swap", "get_options", "get_player_workload")


class ChatBackend(Protocol):
    async def run(
        self,
        agent: str,
        instructions: str,
        prompt: str,
        *,
        model: str,
        use_tools: bool = False,
    ) -> str: ...


class AgentFrameworkBackend:
    def __init__(self, settings: Settings, mcp_url: str) -> None:
        self.settings = settings
        self.mcp_url = mcp_url
        self._clients: dict[str, Any] = {}

    def _client(self, model: str) -> Any:
        if model not in self._clients:
            from agent_framework.openai import OpenAIChatClient

            self._clients[model] = OpenAIChatClient(
                model=model,
                azure_endpoint=self.settings.azure_openai_endpoint,
                api_key=self.settings.azure_openai_api_key,
            )
        return self._clients[model]

    def _options(self, model: str) -> dict[str, Any]:
        opts: dict[str, Any] = {"max_tokens": 600}
        if model != self.settings.azure_openai_deployment_fallback:  # gpt-4.1 has no reasoning
            opts["reasoning"] = {"effort": self.settings.azure_openai_reasoning_effort}
        return opts

    async def run(
        self,
        agent: str,
        instructions: str,
        prompt: str,
        *,
        model: str,
        use_tools: bool = False,
    ) -> str:
        from agent_framework import Agent, MCPStreamableHTTPTool

        tools: Sequence[Any] = ()
        if use_tools:
            mcp = MCPStreamableHTTPTool(
                name="decision_lens", url=self.mcp_url, allowed_tools=list(MCP_TOOLS)
            )
            async with mcp:
                a = Agent(
                    self._client(model),
                    instructions,
                    name=agent,
                    tools=[mcp],
                    default_options=self._options(model),
                )
                return (await a.run(prompt)).text
        a = Agent(
            self._client(model),
            instructions,
            name=agent,
            tools=list(tools),
            default_options=self._options(model),
        )
        return (await a.run(prompt)).text


def build_backend(settings: Settings, mcp_url: str) -> ChatBackend | None:
    if not (settings.azure_openai_endpoint and settings.azure_openai_api_key):
        log.info("no Azure OpenAI endpoint/key: cards will be engine templates")
        return None
    return AgentFrameworkBackend(settings, mcp_url)
