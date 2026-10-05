"""Tavily refusing (credits used up, bad key) falls back to the free search instead of failing the run."""
from __future__ import annotations

from intel.cache import DiskCache
from intel.search import SearchHit, SearchProvider, TavilySearch
from intel.store import MemoryStore


class Fallback(SearchProvider):
    name = "fallback"

    def _search(self, query, include_domains, news_days, exclude_domains=None):
        return [SearchHit(f"https://example.org/{query}", query, f"about {query}")]


class Resp:
    def __init__(self, status: int):
        self.status_code = status


def test_refused_tavily_switches_to_fallback_for_the_rest_of_the_run(monkeypatch):
    posts = []
    monkeypatch.setattr("intel.search.requests.post", lambda *a, **k: posts.append(1) or Resp(432))
    cache = DiskCache(MemoryStore(), ttl_hours=0)
    tavily = TavilySearch("key", cache, max_results=3, fallback=Fallback(cache, 3))

    assert [h.url for h in tavily.search("acme pricing")] == ["https://example.org/acme pricing"]
    assert [h.url for h in tavily.search("acme reviews")] == ["https://example.org/acme reviews"]
    assert tavily.refused
    assert len(posts) == 1 and tavily.api_calls == 1  # no more Tavily calls once it refused


def test_refused_tavily_without_fallback_returns_nothing(monkeypatch):
    monkeypatch.setattr("intel.search.requests.post", lambda *a, **k: Resp(401))
    tavily = TavilySearch("key", DiskCache(MemoryStore(), ttl_hours=0), max_results=3)
    assert tavily.search("acme") == []
