from __future__ import annotations

import json
import logging
import os
import time
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

    def structured(self, *, system: str, user: str, schema: type[T], effort: str = "medium", max_tokens: int = 8000, _retry: bool = False) -> T:
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
        data = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=body)
                    if resp.status_code == 400 and self._json_mode:
                        self._json_mode = False
                        body.pop("response_format", None)
                        resp = client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=body)
                    if resp.status_code in (408, 409, 429, 500, 502, 503, 504, 520, 524) and attempt < 2:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    break
            except httpx.HTTPStatusError as exc:
                raise LLMError(f"OpenAI 兼容接口错误 {exc.response.status_code}: {exc.response.text[:300]}") from exc
            except httpx.HTTPError as exc:
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError(f"无法连接 OpenAI 兼容接口: {exc}") from exc
        if data is None:
            raise LLMError("OpenAI 兼容接口持续不可用")
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"OpenAI 兼容接口返回了意外结构: {str(data)[:200]}") from exc
        try:
            return parse_model(schema, text)
        except LLMError as exc:
            if _retry:
                raise
            log.warning("structured output invalid (%s); retrying once with a stricter instruction", str(exc)[:120])
            return self.structured(system=system, user=user + "\n\n（上一次输出不是合法 JSON：字符串内的反斜杠必须写成 \\\\，不要输出注释或多余文字。）", schema=schema, effort=effort, max_tokens=max_tokens, _retry=True)

    def complete(self, *, system: str, user: str, max_tokens: int = 4000) -> str:
        return "".join(self.stream(system=system, messages=[{"role": "user", "content": user}], max_tokens=max_tokens))

    def stream(self, *, system: str, messages: list[dict[str, str]], max_tokens: int = 6000) -> Iterator[str]:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "stream": True,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    with client.stream("POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=body) as resp:
                        if resp.status_code in (408, 409, 429, 500, 502, 503, 504, 520, 524) and attempt < 2:
                            time.sleep(1.5 * (attempt + 1))
                            continue
                        if resp.status_code >= 400:
                            detail = resp.read().decode("utf-8", "ignore")[:300]
                            raise LLMError(f"OpenAI 兼容接口错误 {resp.status_code}: {detail}")
                        yield from self._iter_sse(resp)
                        return
            except httpx.HTTPError as exc:
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError(f"无法连接 OpenAI 兼容接口: {exc}") from exc

    @staticmethod
    def _iter_sse(resp) -> Iterator[str]:
        if True:
            if True:
                if True:
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
