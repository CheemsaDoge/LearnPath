"""Hidden retries + graceful fallbacks for every LLM-backed feature.

Design rule (product): the learner should never be blocked by a transient model/network error. Every call goes through
``call_with_retries``; when all attempts fail, callers fall back to deterministic content (source-based lesson, generic
quiz, …) and flag it with ``degraded=True`` so the UI can offer a quiet "重新生成" instead of an error page.
"""
from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

from app.llm.base import LLMError

log = logging.getLogger(__name__)
T = TypeVar("T")

NON_RETRYABLE_MARKERS = ("refusal", "拒绝", "鉴权失败", "AuthenticationError")


def is_retryable(exc: Exception) -> bool:
    text = str(exc)
    return not any(marker in text for marker in NON_RETRYABLE_MARKERS)


def call_with_retries(fn: Callable[[], T], *, attempts: int = 3, base_delay: float = 1.5, label: str = "llm") -> T:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except LLMError as exc:
            last = exc
            if not is_retryable(exc) or attempt == attempts:
                break
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            log.warning("%s attempt %d/%d failed (%s); retrying in %.1fs", label, attempt, attempts, str(exc)[:160], delay)
            time.sleep(delay)
        except Exception as exc:  # unexpected provider bug → treat like a transient failure
            last = LLMError(str(exc)[:300])
            if attempt == attempts:
                break
            log.exception("%s attempt %d/%d crashed; retrying", label, attempt, attempts)
            time.sleep(base_delay)
    assert last is not None
    raise last
