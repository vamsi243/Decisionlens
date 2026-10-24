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

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2025-04-01-preview"
    azure_openai_deployment_mini: str = "gpt-5.4-mini"
    azure_openai_deployment_nano: str = "gpt-5.4-nano"
    azure_openai_deployment_fallback: str = "gpt-4.1-mini"
    azure_openai_reasoning_effort: str = "minimal"

    azure_translator_endpoint: str = "https://api.cognitive.microsofttranslator.com"
    azure_translator_key: str = ""
    azure_translator_region: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
