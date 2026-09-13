from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["LEARNPATH_SKIP_DOTENV"] = "1"
os.environ["LEARNPATH_LLM_PROVIDER"] = "mock"
os.environ["LEARNPATH_DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"
os.environ["LEARNPATH_ZHIHU_SEARCH_BACKENDS"] = "brave"
os.environ.pop("ZHIHU_ACCESS_SECRET", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.services import deps, graph_builder
from app.services import profile as profile_service
from app.zhihu.models import PageContent, SearchHit


class FakeSearch:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def search(self, query: str, limit: int = 6) -> list[SearchHit]:
        self.calls.append(query)
        slug = abs(hash(query)) % 100000
        return [
            SearchHit(url=f"https://zhuanlan.zhihu.com/p/{slug}1", title=f"{query} 详解", snippet=f"关于{query}的高赞文章摘要。", kind="article", backend="brave"),
            SearchHit(url=f"https://www.zhihu.com/question/{slug}2", title=f"如何理解{query}？", snippet=f"关于{query}的问题摘要。", kind="question", backend="brave"),
            SearchHit(url="https://www.zhihu.com/topic/1", title="话题页", snippet="", kind="other", backend="brave"),
        ][:limit]


class FakeReader:
    def fetch(self, url: str) -> PageContent:
        if "question" in url:
            return PageContent(url=url, title="问题页", text="这是问题页正文。\n\n回答者甲：先建立直觉。\n\n赞同 1,234", votes=1234, author="甲")
        return PageContent(url=url, title="专栏文章", text="这是专栏正文，包含定义、例子和常见误区。")


@pytest.fixture(scope="session")
def fake_search() -> FakeSearch:
    return FakeSearch()


@pytest.fixture(scope="session", autouse=True)
def _wire(fake_search: FakeSearch):
    dbmod.reset_engine_for_tests(os.environ["LEARNPATH_DATABASE_URL"])
    deps.get_search = lambda: fake_search  # type: ignore[assignment]
    deps.get_reader = lambda: FakeReader()  # type: ignore[assignment]
    graph_builder.get_search = lambda: fake_search  # type: ignore[assignment]
    graph_builder.get_reader = lambda: FakeReader()  # type: ignore[assignment]
    graph_builder.start_pipeline = graph_builder.run_pipeline  # run synchronously in tests
    profile_service.ASYNC_EXTRACTION = False
    yield


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    with TestClient(app) as c:
        yield c
