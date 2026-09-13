from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from typing import TypeVar

import httpx
from pydantic import BaseModel

from app.llm.base import LLMError, parse_model, schema_instructions

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleProvider:
    """Any OpenAI-compatible chat endpoint (DeepSeek, Qwen/DashScope, Kimi, Ollama, ...)."""

    name = "openai"

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None, timeout: float = 180.0) -> None:
        self.model = model
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.timeout = timeout
        self._json_mode = True

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def structured(self, *, system: str, user: str, schema: type[T], effort: str = "medium", max_tokens: int = 8000) -> T:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system + "\n\n" + schema_instructions(schema)},
                {"role": "user", "content": user},
            ],
        }
        if self._json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=body)
                if resp.status_code == 400 and self._json_mode:
                    self._json_mode = False
                    body.pop("response_format", None)
                    resp = client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"OpenAI 兼容接口错误 {exc.response.status_code}: {exc.response.text[:300]}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"无法连接 OpenAI 兼容接口: {exc}") from exc
        text = data["choices"][0]["message"]["content"]
        return parse_model(schema, text)

    def complete(self, *, system: str, user: str, max_tokens: int = 4000) -> str:
        return "".join(self.stream(system=system, messages=[{"role": "user", "content": user}], max_tokens=max_tokens))

    def stream(self, *, system: str, messages: list[dict[str, str]], max_tokens: int = 6000) -> Iterator[str]:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "stream": True,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream("POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=body) as resp:
                    if resp.status_code >= 400:
                        detail = resp.read().decode("utf-8", "ignore")[:300]
                        raise LLMError(f"OpenAI 兼容接口错误 {resp.status_code}: {detail}")
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            event = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        for choice in event.get("choices", []):
                            delta = (choice.get("delta") or {}).get("content")
                            if delta:
                                yield delta
        except httpx.HTTPError as exc:
            raise LLMError(f"无法连接 OpenAI 兼容接口: {exc}") from exc
