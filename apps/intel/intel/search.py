"""Search providers (Tavily, DuckDuckGo) + page fetching, behind one interface."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
import trafilatura

from .cache import DiskCache

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


@dataclass
class SearchHit:
    url: str
    title: str
    content: str  # full page text when available, else snippet
    published: str | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def fetch_page(url: str, cache: DiskCache, timeout: int = 15) -> str:
    """Download a page and extract its main readable text."""

    def _fetch() -> str:
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            if r.status_code >= 400 or "html" not in r.headers.get("content-type", "html"):
                return ""
            text = trafilatura.extract(
                r.text, include_tables=True, include_comments=False, favor_recall=True
            )
            return text or ""
        except requests.RequestException as e:
            log.debug("fetch failed %s: %s", url, e)
            return ""

    return cache.get_or_set("pages", url, _fetch) or ""


class SearchProvider:
    name = "base"

    def __init__(self, cache: DiskCache, max_results: int):
        self.cache = cache
        self.max_results = max_results
        self.api_calls = 0  # real provider calls (cache misses), for the daily budget

    def search(
        self,
        query: str,
        include_domains: list[str] | None = None,
        news_days: int | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[SearchHit]:
        key = {"p": self.name, "q": query, "d": include_domains, "n": news_days, "k": self.max_results}
        if exclude_domains:  # only in the key when set, so existing cache entries stay valid
            key["x"] = sorted(exclude_domains)
        raw = self.cache.get_or_set(
            "search", key,
            lambda: [h.to_dict() for h in self._search(query, include_domains, news_days, exclude_domains)],
        )
        hits = [SearchHit(**h) for h in raw or []]
        if exclude_domains:  # providers treat exclusions as a hint; enforce them
            hits = [h for h in hits if not any(domain_of(h.url).endswith(d) for d in exclude_domains)]
        return hits

    def _search(self, query, include_domains, news_days, exclude_domains=None) -> list[SearchHit]:  # pragma: no cover
        raise NotImplementedError


class TavilySearch(SearchProvider):
    """Best quality for the money: search + cleaned page content in one call.
    Basic depth = 1 credit per query (free tier: 1,000 credits/month)."""

    name = "tavily"
    URL = "https://api.tavily.com/search"
    # 401 bad key, 432 plan credits used up, 433 pay-as-you-go limit: retrying won't help
    REFUSED = (401, 403, 432, 433)

    def __init__(self, api_key: str, cache: DiskCache, max_results: int, fallback: SearchProvider | None = None):
        super().__init__(cache, max_results)
        self.api_key = api_key
        self.fallback = fallback
        self.refused = False  # once Tavily refuses, the rest of the run goes straight to the fallback

    def _fall_back(self, query, include_domains, news_days, exclude_domains):
        return self.fallback._search(query, include_domains, news_days, exclude_domains) if self.fallback else []

    def _search(self, query, include_domains, news_days, exclude_domains=None):
        if self.refused:
            return self._fall_back(query, include_domains, news_days, exclude_domains)
        self.api_calls += 1
        body = {
            "query": query,
            "max_results": self.max_results,
            "search_depth": "basic",
            "include_raw_content": "markdown",
        }
        if include_domains:
            body["include_domains"] = include_domains
        if exclude_domains:
            body["exclude_domains"] = exclude_domains
        if news_days:
            body["topic"] = "news"
            body["days"] = news_days
        for attempt in range(3):
            try:
                r = requests.post(
                    self.URL,
                    json=body,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=40,
                )
                if r.status_code == 429:
                    time.sleep(2 ** attempt * 2)
                    continue
                if r.status_code in self.REFUSED:
                    log.warning("Tavily refused the request (HTTP %s) - using DuckDuckGo for the rest of this run",
                                r.status_code)
                    self.refused = True
                    return self._fall_back(query, include_domains, news_days, exclude_domains)
                r.raise_for_status()
                hits = []
                for res in r.json().get("results", []):
                    content = res.get("raw_content") or res.get("content") or ""
                    hits.append(
                        SearchHit(
                            url=res["url"],
                            title=res.get("title", ""),
                            content=content,
                            published=res.get("published_date"),
                        )
                    )
                return hits
            except requests.RequestException as e:
                log.warning("Tavily error for %r: %s", query, e)
                time.sleep(1.5)
        return self._fall_back(query, include_domains, news_days, exclude_domains)


class DuckDuckGoSearch(SearchProvider):
    """Free fallback: DuckDuckGo results, then we fetch & extract each page ourselves."""

    name = "ddg"

    def _search(self, query, include_domains, news_days, exclude_domains=None):
        self.api_calls += 1
        from ddgs import DDGS

        q = query
        if include_domains:
            q += " " + " OR ".join(f"site:{d}" for d in include_domains)
        if exclude_domains:
            q += " " + " ".join(f"-site:{d}" for d in exclude_domains)
        results: list[dict] = []
        for attempt in range(3):
            try:
                with DDGS() as ddgs:
                    if news_days:
                        timelimit = "w" if news_days <= 7 else "m" if news_days <= 31 else "y"
                        results = list(ddgs.news(q, max_results=self.max_results, timelimit=timelimit))
                    else:
                        results = list(ddgs.text(q, max_results=self.max_results))
                break
            except Exception as e:  # ddgs raises its own rate-limit exceptions
                log.warning("DuckDuckGo error for %r: %s", query, e)
                time.sleep(2 ** attempt * 2)

        hits = []
        for res in results:
            url = res.get("href") or res.get("url")
            if not url:
                continue
            if include_domains and not any(domain_of(url).endswith(d) for d in include_domains):
                continue
            if exclude_domains and any(domain_of(url).endswith(d) for d in exclude_domains):
                continue
            snippet = res.get("body", "")
            page = fetch_page(url, self.cache)
            hits.append(
                SearchHit(
                    url=url,
                    title=res.get("title", ""),
                    content=page if len(page) > len(snippet) else snippet,
                    published=res.get("date"),
                )
            )
        return hits


def make_search_provider(cfg, cache: DiskCache) -> SearchProvider:
    if cfg.resolved_search_provider == "tavily":
        return TavilySearch(cfg.tavily_api_key, cache, cfg.results_per_query,
                            fallback=DuckDuckGoSearch(cache, cfg.results_per_query))
    return DuckDuckGoSearch(cache, cfg.results_per_query)
