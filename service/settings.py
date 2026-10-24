"""Typed settings read from the environment / .env."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    run_mode: Literal["local", "azure"] = "local"
    match_dir: str = "data/samples/match_42"
    replay_speed: float = 1.0
    replay_autoplay: bool = False
    precompute_analysis: bool = True

    # Agents (Phase 6)
    mcp_url: str = "http://127.0.0.1:8000/mcp/"  # where the agents reach the engine tools
    agent_timeout_s: float = 25.0
    agent_cache_path: str = "data/cache/agent_responses.json"

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2025-04-01-preview"
    azure_openai_deployment_mini: str = "gpt-5.4-mini"
    azure_openai_deployment_nano: str = "gpt-5.4-nano"
    azure_openai_deployment_fallback: str = "gpt-4.1-mini"
    azure_openai_reasoning_effort: str = "minimal"

    azure_translator_endpoint: str = "https://api.cognitive.microsofttranslator.com"

    # Azure (Phase 8): all reached with the app's managed identity, no keys
    eventhub_namespace: str = ""  # fully qualified, e.g. evhns-x.servicebus.windows.net
    eventhub_name: str = "match"
    eventhub_consumer_group: str = "$Default"
    broadcast_producer: bool = True  # run the replay job that feeds Event Hubs in-process
    live_simulation: bool = False  # local: run the live-broadcast path without Event Hubs
    cosmos_endpoint: str = ""
    cosmos_database: str = "decisionlens"
    cosmos_container: str = "state"
    signalr_endpoint: str = ""  # e.g. https://sigr-x.service.signalr.net
    signalr_hub: str = "decisionlens"
    applicationinsights_connection_string: str = ""
    use_managed_identity_for_openai: bool = False
    azure_translator_key: str = ""
    azure_translator_region: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
