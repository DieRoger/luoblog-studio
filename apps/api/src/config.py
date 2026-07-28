"""Application configuration via pydantic-settings.

All settings are loaded from environment variables with sensible defaults.
See .env.example for the full list.
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_secret: str = "change-me-in-production"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://luoblog:luoblog@localhost:5432/luoblog"
    database_sync_url: str = "postgresql://luoblog:luoblog@localhost:5432/luoblog"

    # --- LLM ---
    llm_provider: Literal["deepseek", "openai"] = "deepseek"
    llm_model: str = "deepseek-chat"
    deepseek_api_key: str = ""
    openai_api_key: str = ""

    # --- Embedding ---
    embedding_mode: Literal["local", "api"] = "local"
    embedding_local_model: str = "BAAI/bge-m3"
    embedding_api_model: str = "text-embedding-3-small"

    # --- Workspace ---
    workspace_root: str = str(Path.home() / "luoblog-workspace")

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Logging ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"


# Singleton — import this everywhere
settings = Settings()
