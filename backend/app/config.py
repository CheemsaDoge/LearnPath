from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime configuration. Every field can be set as LEARNWAY_<NAME> in the env or .env."""

    model_config = SettingsConfigDict(
        env_prefix="LEARNWAY_",
        env_file=(BACKEND_DIR / ".env", REPO_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: str = "auto"  # auto | anthropic | openai | mock
    anthropic_model: str = "claude-opus-5"
    anthropic_betas: str = ""  # comma separated
    openai_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 180.0

    # Zhihu content
    zhihu_open_api_base: str = ""
    zhihu_open_api_key: str = ""
    zhihu_search_backends: str = "brave-api,jina,brave,so360,bing"
    reader_base: str = "https://r.jina.ai"
    sources_per_node: int = 4
    fetch_full_text_per_node: int = 2
    grounding_concurrency: int = 2
    search_pause_seconds: float = 1.2
    http_timeout_seconds: float = 25.0

    # Storage / serving
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'learnway.db').as_posix()}"
    frontend_dist: str = str(REPO_DIR / "frontend" / "dist")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- derived helpers ----
    @property
    def resolved_llm_provider(self) -> str:
        if self.llm_provider != "auto":
            return self.llm_provider
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            return "anthropic"
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        return "mock"

    @property
    def anthropic_beta_list(self) -> list[str]:
        return [b.strip() for b in self.anthropic_betas.split(",") if b.strip()]

    @property
    def search_backend_list(self) -> list[str]:
        return [b.strip().lower() for b in self.zhihu_search_backends.split(",") if b.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
