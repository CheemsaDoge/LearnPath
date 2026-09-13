from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime configuration. Every field can be set as LEARNPATH_<NAME> in the env or .env."""

    model_config = SettingsConfigDict(
        env_prefix="LEARNPATH_",
        env_file=(BACKEND_DIR / ".env", REPO_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: str = "auto"  # auto | anthropic | openai | mock
    anthropic_model: str = "claude-opus-5"
    anthropic_betas: str = ""  # comma separated
    anthropic_api_key: str = Field(default="", validation_alias=AliasChoices("ANTHROPIC_API_KEY", "LEARNPATH_ANTHROPIC_API_KEY"))
    anthropic_auth_token: str = Field(default="", validation_alias=AliasChoices("ANTHROPIC_AUTH_TOKEN", "LEARNPATH_ANTHROPIC_AUTH_TOKEN"))
    anthropic_base_url: str = Field(default="", validation_alias=AliasChoices("ANTHROPIC_BASE_URL", "LEARNPATH_ANTHROPIC_BASE_URL"))
    openai_api_key: str = Field(default="", validation_alias=AliasChoices("OPENAI_API_KEY", "LEARNPATH_OPENAI_API_KEY"))
    openai_base_url: str = Field(default="", validation_alias=AliasChoices("OPENAI_BASE_URL", "LEARNPATH_OPENAI_BASE_URL"))
    openai_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 180.0

    # Zhihu content — 知乎数据开放平台 Access Secret (https://developer.zhihu.com/profile)
    zhihu_access_secret: str = Field(default="", validation_alias=AliasChoices("ZHIHU_ACCESS_SECRET", "LEARNPATH_ZHIHU_ACCESS_SECRET"))
    zhida_model: str = "zhida-fast-1p5"
    hot_cache_seconds: int = 1800
    zhihu_search_backends: str = "brave-api,jina,brave,so360,bing"
    reader_base: str = "https://r.jina.ai"
    # Third-party keys (un-prefixed names accepted for convenience; never logged)
    jina_api_key: str = Field(default="", validation_alias=AliasChoices("JINA_API_KEY", "LEARNPATH_JINA_API_KEY"))
    brave_search_api_key: str = Field(default="", validation_alias=AliasChoices("BRAVE_SEARCH_API_KEY", "LEARNPATH_BRAVE_SEARCH_API_KEY"))
    sources_per_node: int = 4
    fetch_full_text_per_node: int = 2
    grounding_concurrency: int = 0  # 0 = auto: 4 with official/Jina keys, else 2 (anonymous backends rate-limit)
    search_pause_seconds: float = 1.2
    http_timeout_seconds: float = 25.0

    # Zhihu OAuth (测试状态 — see docs/zhihu-oauth.md). App ID / App Key are issued on the hackathon project page.
    public_origin: str = "http://127.0.0.1:8000"
    session_secret: str = "change-me-in-production"
    zhihu_oauth_app_id: str = Field(default="", validation_alias=AliasChoices("ZHIHU_OAUTH_APP_ID", "LEARNPATH_ZHIHU_OAUTH_APP_ID"))
    zhihu_oauth_app_key: str = Field(default="", validation_alias=AliasChoices("ZHIHU_OAUTH_APP_KEY", "LEARNPATH_ZHIHU_OAUTH_APP_KEY"))
    zhihu_oauth_redirect_uri: str = Field(default="", validation_alias=AliasChoices("ZHIHU_OAUTH_REDIRECT_URI", "LEARNPATH_ZHIHU_OAUTH_REDIRECT_URI"))
    zhihu_oauth_authorize_url: str = "https://openapi.zhihu.com/authorize"
    zhihu_oauth_token_url: str = "https://openapi.zhihu.com/access_token"
    zhihu_oauth_userinfo_url: str = "https://openapi.zhihu.com/user"
    zhihu_oauth_require_state: bool = True  # hackathon OAuth passes `state` through; set False only if the platform drops it

    # Storage / serving
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'learnpath.db').as_posix()}"
    frontend_dist: str = str(REPO_DIR / "frontend" / "dist")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- derived helpers ----
    @property
    def resolved_llm_provider(self) -> str:
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.anthropic_api_key or self.anthropic_auth_token:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "mock"

    @property
    def anthropic_beta_list(self) -> list[str]:
        return [b.strip() for b in self.anthropic_betas.split(",") if b.strip()]

    @property
    def search_backend_list(self) -> list[str]:
        return [b.strip().lower() for b in self.zhihu_search_backends.split(",") if b.strip()]

    @property
    def effective_grounding_concurrency(self) -> int:
        if self.grounding_concurrency > 0:
            return self.grounding_concurrency
        return 4 if (self.zhihu_access_secret or self.jina_api_key or self.brave_search_api_key) else 2

    @property
    def zhihu_oauth_enabled(self) -> bool:
        return bool(self.zhihu_oauth_app_id and self.zhihu_oauth_app_key)

    @property
    def resolved_redirect_uri(self) -> str:
        return self.zhihu_oauth_redirect_uri or f"{self.public_origin.rstrip('/')}/api/auth/zhihu/callback"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    import os

    if os.environ.get("LEARNPATH_SKIP_DOTENV"):  # test-suite: never read the developer's real .env
        return Settings(_env_file=None)
    return Settings()
