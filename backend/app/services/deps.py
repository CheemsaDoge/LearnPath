from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.zhihu.official import ZhihuOpenPlatform
from app.zhihu.reader import PageReader
from app.zhihu.search import ZhihuSearch, configure_keys


@lru_cache
def get_official() -> ZhihuOpenPlatform:
    s = get_settings()
    return ZhihuOpenPlatform(base=s.zhihu_open_api_base, api_key=s.zhihu_open_api_key, timeout=s.http_timeout_seconds)


@lru_cache
def get_search() -> ZhihuSearch:
    s = get_settings()
    configure_keys(JINA_API_KEY=s.jina_api_key, BRAVE_SEARCH_API_KEY=s.brave_search_api_key)
    return ZhihuSearch(backends=s.search_backend_list, official=get_official(), timeout=s.http_timeout_seconds, pause=s.search_pause_seconds)


@lru_cache
def get_reader() -> PageReader:
    s = get_settings()
    return PageReader(base=s.reader_base, api_key=s.jina_api_key or None, timeout=max(s.http_timeout_seconds, 45.0))


def reset_deps_cache() -> None:
    get_official.cache_clear()
    get_search.cache_clear()
    get_reader.cache_clear()
