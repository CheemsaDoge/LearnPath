from __future__ import annotations

import os
from functools import lru_cache

from app.config import get_settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider
from app.llm.mock_provider import MockProvider
from app.llm.openai_provider import OpenAICompatibleProvider


@lru_cache
def get_llm() -> LLMProvider:
    settings = get_settings()
    provider = settings.resolved_llm_provider
    if provider == "anthropic":
        return AnthropicProvider(model=settings.anthropic_model, betas=settings.anthropic_beta_list, timeout=settings.llm_timeout_seconds)
    if provider == "openai":
        return OpenAICompatibleProvider(model=settings.openai_model, base_url=os.environ.get("OPENAI_BASE_URL"), api_key=os.environ.get("OPENAI_API_KEY"), timeout=settings.llm_timeout_seconds)
    return MockProvider()


def reset_llm_cache() -> None:
    get_llm.cache_clear()
