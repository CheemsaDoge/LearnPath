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


_VALID_ESCAPE = set('"\\/bfnrtu')


def repair_json(raw: str) -> str:
    """Fix the most common LLM JSON defects: invalid backslash escapes (LaTeX like \\oint, \\frac),
    raw newlines inside strings, and trailing commas."""
    out: list[str] = []
    in_str = False
    i = 0
    while i < len(raw):
        ch = raw[i]
        if in_str:
            if ch == "\\":
                nxt = raw[i + 1] if i + 1 < len(raw) else ""
                if nxt in _VALID_ESCAPE:
                    out.append(ch + nxt)
                    i += 2
                    continue
                out.append("\\\\")  # lone backslash → escaped backslash
                i += 1
                continue
            if ch == '"':
                in_str = False
            elif ch == "\n":
                out.append("\\n")
                i += 1
                continue
            elif ch == "\t":
                out.append("\\t")
                i += 1
                continue
            out.append(ch)
        else:
            if ch == '"':
                in_str = True
            out.append(ch)
        i += 1
    fixed = "".join(out)
    fixed = re.sub(r",(\s*[}\]])", r"\1", fixed)
    return fixed


# LaTeX commands whose first letter collides with a JSON escape (\b \f \n \r \t). When a model writes
# "\frac" inside a JSON string, strict parsing yields form-feed + "rac"; we double the backslash first.
_LATEX_AMBIGUOUS = (
    "frac", "forall", "flat", "fbox", "beta", "binom", "bar", "boldsymbol", "bigl", "bigr", "begin", "bmod", "bullet", "bigcup", "bigcap",
    "nabla", "neq", "nu", "ne", "not", "notin", "nmid", "newline", "rho", "right", "rightarrow", "rangle", "rfloor", "rceil",
    "theta", "tan", "times", "tau", "text", "tfrac", "to", "tilde", "top", "triangle", "textbf", "textit", "tanh",
)
_LATEX_RE = re.compile(r"(?<!\\)\\(" + "|".join(sorted(_LATEX_AMBIGUOUS, key=len, reverse=True)) + r")(?![A-Za-z])")


def fix_latex_escapes(raw: str) -> str:
    return _LATEX_RE.sub(lambda m: "\\\\" + m.group(1), raw)


def parse_model(schema: type[T], text: str) -> T:
    raw = fix_latex_escapes(extract_json(text))
    try:
        return schema.model_validate_json(raw)
    except Exception as exc:
        try:
            return schema.model_validate_json(repair_json(raw))
        except Exception:
            try:
                return schema.model_validate(json.loads(repair_json(raw)))
            except Exception:
                raise LLMError(f"模型输出不符合 {schema.__name__} 结构: {str(exc)[:300]}") from exc


def schema_instructions(schema: type[BaseModel]) -> str:
    return (
        "只输出一个 JSON 对象，不要输出任何解释或 Markdown 代码块。JSON 必须严格符合以下 JSON Schema：\n"
        + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    )
