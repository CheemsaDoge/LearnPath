from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.llm.base import LLMError, parse_model, schema_instructions

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# Models that accept output_config.effort (Claude 4.6 and newer).
_EFFORT_MODEL_HINTS = ("fable", "mythos", "opus-5", "sonnet-5", "opus-4-6", "opus-4-7", "opus-4-8", "sonnet-4-6", "opus-4.6", "opus-4.7", "sonnet-4.6")


class AnthropicProvider:
    """Claude through the official Anthropic SDK.

    Credentials/base URL come from ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL.
    Structured outputs use ``client.messages.parse``; if the upstream (e.g. a third-party relay)
    rejects the request we transparently fall back to prompt-guided JSON.
    """

    name = "anthropic"

    def __init__(self, model: str, betas: list[str] | None = None, timeout: float = 180.0, api_key: str | None = None, auth_token: str | None = None, base_url: str | None = None) -> None:
        self.model = model
        self.betas = betas or []
        kwargs: dict = {"timeout": timeout, "max_retries": 2}
        if api_key:
            kwargs["api_key"] = api_key
        if auth_token:
            kwargs["auth_token"] = auth_token
        if base_url:
            kwargs["base_url"] = base_url
        self.client = anthropic.Anthropic(**kwargs)
        self._structured_mode = "native"  # native | prompt
        self._effort_supported = True

    # ------------------------------------------------------------------ helpers
    def _extra_headers(self) -> dict[str, str]:
        return {"anthropic-beta": ",".join(self.betas)} if self.betas else {}

    def _effort_kwargs(self, effort: str) -> dict:
        if effort and self._effort_supported and any(h in self.model for h in _EFFORT_MODEL_HINTS):
            return {"output_config": {"effort": effort}}
        return {}

    @staticmethod
    def _text_of(message) -> str:
        if getattr(message, "stop_reason", None) == "refusal":
            raise LLMError("模型拒绝了这次请求（safety refusal），请调整学习目标后重试")
        return "".join(block.text for block in message.content if getattr(block, "type", "") == "text")

    def _wrap(self, exc: Exception) -> LLMError:
        if isinstance(exc, anthropic.AuthenticationError):
            return LLMError("Anthropic 鉴权失败：请检查 ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN")
        if isinstance(exc, anthropic.RateLimitError):
            return LLMError("Anthropic 触发限流，请稍后重试")
        if isinstance(exc, anthropic.APIStatusError):
            return LLMError(f"Anthropic 接口错误 {exc.status_code}: {str(exc)[:300]}")
        if isinstance(exc, anthropic.APIConnectionError):
            return LLMError("无法连接 Anthropic 接口，请检查网络或 ANTHROPIC_BASE_URL")
        return LLMError(str(exc)[:300])

    # ------------------------------------------------------------------ API
    def structured(self, *, system: str, user: str, schema: type[T], effort: str = "medium", max_tokens: int = 8000) -> T:
        if self._structured_mode == "native":
            try:
                message = self.client.messages.parse(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    output_format=schema,
                    extra_headers=self._extra_headers(),
                    **self._effort_kwargs(effort),
                )
                if getattr(message, "stop_reason", None) == "refusal":
                    raise LLMError("模型拒绝了这次请求（safety refusal）")
                parsed = getattr(message, "parsed_output", None)
                if parsed is not None:
                    return parsed
                return parse_model(schema, self._text_of(message))
            except anthropic.BadRequestError as exc:
                log.warning("native structured output rejected (%s); falling back to prompt-guided JSON", str(exc)[:160])
                self._structured_mode = "prompt"
            except LLMError:
                raise
            except Exception as exc:  # network / auth / 5xx
                raise self._wrap(exc) from exc
        return self._structured_via_prompt(system=system, user=user, schema=schema, effort=effort, max_tokens=max_tokens)

    def _structured_via_prompt(self, *, system: str, user: str, schema: type[T], effort: str, max_tokens: int) -> T:
        text = self.complete(system=system + "\n\n" + schema_instructions(schema), user=user, max_tokens=max_tokens, effort=effort)
        return parse_model(schema, text)

    def complete(self, *, system: str, user: str, max_tokens: int = 4000, effort: str = "medium") -> str:
        chunks: list[str] = []
        for delta in self.stream(system=system, messages=[{"role": "user", "content": user}], max_tokens=max_tokens, effort=effort):
            chunks.append(delta)
        return "".join(chunks)

    def stream(self, *, system: str, messages: list[dict[str, str]], max_tokens: int = 6000, effort: str = "medium") -> Iterator[str]:
        for attempt in range(2):
            try:
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                    extra_headers=self._extra_headers(),
                    **self._effort_kwargs(effort),
                ) as stream:
                    for text in stream.text_stream:
                        yield text
                    final = stream.get_final_message()
                    if final.stop_reason == "refusal":
                        raise LLMError("模型拒绝了这次请求（safety refusal）")
                return
            except anthropic.BadRequestError as exc:
                if attempt == 0 and self._effort_supported and "output_config" in str(exc):
                    log.warning("upstream rejected output_config.effort; disabling effort control")
                    self._effort_supported = False
                    continue
                raise self._wrap(exc) from exc
            except LLMError:
                raise
            except Exception as exc:
                raise self._wrap(exc) from exc
