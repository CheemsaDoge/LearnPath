from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
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
    # Third-party keys (un-prefixed names accepted for convenience; never logged)
    jina_api_key: str = Field(default="", validation_alias=AliasChoices("JINA_API_KEY", "LEARNWAY_JINA_API_KEY"))
    brave_search_api_key: str = Field(default="", validation_alias=AliasChoices("BRAVE_SEARCH_API_KEY", "LEARNWAY_BRAVE_SEARCH_API_KEY"))
    sources_per_node: int = 4
    fetch_full_text_per_node: int = 2
    grounding_concurrency: int = 2
    search_pause_seconds: float = 1.2
    http_timeout_seconds: float = 25.0

    # Zhihu OAuth (测试状态 — see docs/zhihu-oauth.md)
    public_origin: str = "http://127.0.0.1:8000"
    session_secret: str = "change-me-in-production"
    zhihu_oauth_client_id: str = ""
    zhihu_oauth_client_secret: str = ""
    zhihu_oauth_authorize_url: str = ""
    zhihu_oauth_token_url: str = ""
    zhihu_oauth_userinfo_url: str = ""
    zhihu_oauth_scope: str = ""
    zhihu_oauth_redirect_uri: str = ""  # defaults to {public_origin}/api/auth/zhihu/callback

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
    def zhihu_oauth_enabled(self) -> bool:
        return bool(self.zhihu_oauth_client_id and self.zhihu_oauth_authorize_url and self.zhihu_oauth_token_url)

    @property
    def resolved_redirect_uri(self) -> str:
        return self.zhihu_oauth_redirect_uri or f"{self.public_origin.rstrip('/')}/api/auth/zhihu/callback"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
