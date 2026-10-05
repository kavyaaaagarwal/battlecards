import time

from conftest import FakeSearch

from intel.cache import DiskCache
from intel.collect import collect_sources, plan_queries
from intel.config import Company, Config
from intel.search import SearchHit
from intel.store import MemoryStore


def test_query_plan_is_six_searches_per_company():
    qs = plan_queries(Company("Acme", "acme.com"), "help desk", ["acme.com", "rival.io"])
    assert [q.category for q in qs] == ["positioning", "pricing", "news", "reviews", "complaints", "alternatives"]
    reviews = next(q for q in qs if q.category == "reviews")
    assert "rating" in reviews.text  # reviews + star ratings in one search
    assert next(q for q in qs if q.category == "alternatives").exclude_domains == ["acme.com", "rival.io"]


class SlowSearch(FakeSearch):
    """Pricing searches answer instantly; everything else takes far longer than the deadline."""

    def _search(self, query, include_domains, news_days, exclude_domains=None):
        if "pricing" not in query and "official website" not in query:
            time.sleep(2)
        return super()._search(query, include_domains, news_days, exclude_domains)


def test_collection_stops_at_the_deadline_and_keeps_what_it_has(offline):
    cfg = Config(company=Company("Acme", "acme.com"), competitors=[Company("Rival", "rival.io")], category="help desk")
    cache = DiskCache(MemoryStore(), 0)
    stats: dict = {}
    t0 = time.monotonic()
    sources, _ = collect_sources(cfg, SlowSearch(cache, 3), cache, deadline=t0 + 0.5, stats=stats)
    assert time.monotonic() - t0 < 1.5
    assert sources and {s.category for s in sources} == {"pricing"}  # only finished searches are kept
    assert stats["searches_planned"] == 2 * 6 + 1 + 1  # 6 per company + 1 comparison + 1 market
    assert 1 <= stats["searches_done"] < stats["searches_planned"]


class OffTopicSearch(FakeSearch):
    """Review searches return a page about a different company; site-limited searches find nothing."""

    def __init__(self, cache, n):
        super().__init__(cache, n)
        self.queries = []

    def _search(self, query, include_domains, news_days, exclude_domains=None):
        self.queries.append((query, include_domains))
        if "official website" in query:
            return super()._search(query, include_domains, news_days, exclude_domains)
        if include_domains and any(d.endswith("acme.com") for d in include_domains):
            return []  # the company's own site isn't indexed
        if "reviews" in query and query.startswith("Acme"):
            return [SearchHit("https://g2.com/products/workday", "Workday reviews", "Workday is an HCM suite. " * 20)]
        return super()._search(query, include_domains, news_days, exclude_domains)


def test_sources_that_never_mention_the_company_are_dropped(offline):
    cfg = Config(company=Company("Acme", "acme.com"), competitors=[Company("Rival", "rival.io")])
    cache = DiskCache(MemoryStore(), 0)
    sources, _ = collect_sources(cfg, OffTopicSearch(cache, 3), cache)
    assert not any("workday" in s.url for s in sources)
    assert all("acme" in (s.title + s.content).lower() or "acme.com" in s.url for s in sources if s.company == "Acme")


def test_falls_back_to_an_open_search_when_own_site_finds_nothing(offline):
    cfg = Config(company=Company("Acme", "acme.com"), competitors=[Company("Rival", "rival.io")], category="cruise software")
    cache = DiskCache(MemoryStore(), 0)
    search = OffTopicSearch(cache, 3)
    sources, _ = collect_sources(cfg, search, cache)
    assert ('"Acme" cruise software', None) in search.queries
    assert any(s.company == "Acme" and s.category == "positioning" for s in sources)
