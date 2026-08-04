"""Environment configuration. Read once at startup via `get_settings()`."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

SCORING_CONFIG_PATH = Path(__file__).parent / "scoring_config.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    openai_api_key: Optional[str] = None
    perplexity_api_key: Optional[str] = None
    perplexity_model: str = "sonar-pro"
    openai_model: str = "gpt-4o-mini"
    frontend_url: str = "http://localhost:3000"
    use_fixtures: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def load_scoring_config() -> dict:
    with open(SCORING_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
