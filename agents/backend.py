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

            if self.settings.azure_openai_api_key:
                auth: dict[str, Any] = {"api_key": self.settings.azure_openai_api_key}
            else:  # Azure: the app's managed identity (role: Cognitive Services OpenAI User)
                from azure.identity import DefaultAzureCredential

                auth = {"credential": DefaultAzureCredential()}
            self._clients[model] = OpenAIChatClient(
                model=model, azure_endpoint=self.settings.azure_openai_endpoint, **auth
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
    keyed = settings.azure_openai_api_key or settings.use_managed_identity_for_openai
    if not (settings.azure_openai_endpoint and keyed):
        log.info("no Azure OpenAI endpoint/key: cards will be engine templates")
        return None
    return AgentFrameworkBackend(settings, mcp_url)
