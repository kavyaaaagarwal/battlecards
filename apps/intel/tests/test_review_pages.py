from conftest import FakeSearch

from intel.cache import DiskCache
from intel.config import Company
from intel.domain.ratings import verify_ratings
from intel.domain.review_sites import tracked_site
from intel.models import Rating, Source
from intel.review_pages import pins_key, tracked_review_pages
from intel.search import SearchHit
from intel.store import MemoryStore


class CountingSearch(FakeSearch):
    def __init__(self, cache, n):
        super().__init__(cache, n)
        self.lookups = 0

    def _search(self, query, include_domains, news_days, exclude_domains=None):
        self.lookups += 1
        return super()._search(query, include_domains, news_days, exclude_domains)


def test_any_page_of_a_product_resolves_to_its_reviews_page():
    site = tracked_site("https://www.softwareadvice.com/hr/paycor-perform-profile/vs/web-pay")
    assert site.label == "Software Advice"
    assert site.canonical(site.page.search("https://softwareadvice.com/hr/paycor-perform-profile")) == \
        "https://www.softwareadvice.com/hr/paycor-perform-profile/reviews"
    assert tracked_site("https://www.capterra.com/p/86714/WebPay/reviews") is None
    assert tracked_site("https://www.gartner.com/reviews/vendor/paylocity").label == "Gartner Peer Insights"
    assert tracked_site("https://www.gartner.com/reviews/market/hcm/compare/a-vs-b") is None  # two vendors on one page
    assert tracked_site("https://www.g2.com/products/paylocity/reviews") is None


def test_pages_are_found_once_then_reused():
    store = MemoryStore()
    search = CountingSearch(DiskCache(store, 0), 3)
    rival = Company("Rival", "rival.io")
    first = tracked_review_pages([rival], search, store)
    page = "https://www.softwareadvice.com/hr/rival-profile/reviews"
    assert [(s.label, url) for _, s, url, _ in first] == [("Software Advice", page)]
    assert store.get_json(pins_key(rival))["pages"] == {"Software Advice": page}

    search.lookups = 0
    again = tracked_review_pages([rival], search, store)
    assert [url for *_, url, _ in again] == [url for *_, url, _ in first]
    assert search.lookups == 2  # only the sites still without a page (TrustRadius, Gartner) are searched


def test_comparison_pages_are_skipped_and_the_first_page_titled_for_the_company_is_pinned():
    class SoftwareAdvice(FakeSearch):
        def _search(self, query, include_domains, news_days, exclude_domains=None):
            if include_domains != ["softwareadvice.com"]:
                return []
            return [SearchHit(u, "", "") for u in (
                "https://www.softwareadvice.com/hr/paycom-profile/vs/web-pay",  # a comparison, not Paycom's page
                "https://www.softwareadvice.com/hr/paycom-profile/reviews",     # a rival that lists Paylocity
                "https://www.softwareadvice.com/hr/web-pay-profile")]           # Paylocity's own (product name differs)

        def extract(self, urls):
            pages = {"paycom-profile": "# Paycom User Reviews\nAlternatives: Paylocity",
                     "web-pay-profile": "# Paylocity User Reviews\nOverall Rating 4.5"}
            return {u: t for u in urls for k, t in pages.items() if k in u}

    store = MemoryStore()
    got = tracked_review_pages([Company("Paylocity")], SoftwareAdvice(DiskCache(store, 0), 3), store)
    assert [url for *_, url, _ in got] == ["https://www.softwareadvice.com/hr/web-pay-profile/reviews"]


def test_a_page_about_another_product_is_not_pinned():
    class WrongProduct(FakeSearch):
        def extract(self, urls):
            return {u: "# Workday User Reviews\nAlternatives: Rival, ADP\n" + "Workday HCM reviews. " * 20 for u in urls}

    store = MemoryStore()
    assert tracked_review_pages([Company("Rival", "rival.io")], WrongProduct(DiskCache(store, 0), 3), store) == []
    assert store.get_json("review_pages/rival.json") is None


def test_ratings_only_count_from_tracked_pages_and_take_the_sites_name():
    text = "Paylocity Reviews. 4.3 out of 5 from 1,320 reviews"
    by_id = {
        "S1": Source(id="S1", company="P", category="reviews",
                     url="https://www.softwareadvice.com/hr/webpay-profile/reviews", title="", content=text),
        "S2": Source(id="S2", company="P", category="reviews", url="https://www.g2.com/products/p/reviews", title="", content=text),
    }
    kept = verify_ratings([Rating(site="softwareadvice.com", rating=4.3, review_count=1320, source="S1"),
                           Rating(site="G2", rating=4.3, source="S2")], by_id)
    assert [(r.site, r.rating, r.review_count) for r in kept] == [("Software Advice", 4.3, 1320)]


def test_gartner_vendor_page_is_guessed_when_search_misses_it_and_pinned_if_it_loads():
    class GartnerOnly(FakeSearch):
        def _search(self, query, include_domains, news_days, exclude_domains=None):
            return []  # search finds no page on any site

        def extract(self, urls):
            return {u: "Rival has 120 reviews with an overall average rating of 4.1." for u in urls if "gartner" in u}

    store = MemoryStore()
    got = tracked_review_pages([Company("Rival", "rival.io")], GartnerOnly(DiskCache(store, 0), 3), store)
    assert [(s.label, url) for _, s, url, _ in got] == [("Gartner Peer Insights", "https://www.gartner.com/reviews/vendor/rival")]
