from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMProvider(Protocol):
    name: str
    model: str

    def structured(self, *, system: str, user: str, schema: type[T], effort: str = "medium", max_tokens: int = 8000) -> T: ...

    def stream(self, *, system: str, messages: list[dict[str, str]], max_tokens: int = 6000) -> Iterator[str]: ...

    def complete(self, *, system: str, user: str, max_tokens: int = 4000) -> str: ...


def extract_json(text: str) -> str:
    """Pull the first JSON object out of a model reply (tolerates ``` fences and prose)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        return fence.group(1)
    start = text.find("{")
    if start == -1:
        raise LLMError("模型没有返回 JSON")
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def parse_model(schema: type[T], text: str) -> T:
    raw = extract_json(text)
    try:
        return schema.model_validate_json(raw)
    except Exception as exc:  # pragma: no cover - defensive
        try:
            return schema.model_validate(json.loads(raw))
        except Exception:
            raise LLMError(f"模型输出不符合 {schema.__name__} 结构: {exc}") from exc


def schema_instructions(schema: type[BaseModel]) -> str:
    return (
        "只输出一个 JSON 对象，不要输出任何解释或 Markdown 代码块。JSON 必须严格符合以下 JSON Schema：\n"
        + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    )
