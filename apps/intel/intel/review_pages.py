"""A fixed set of review pages per company, so ratings are measured on the same pages every run.

An open "X reviews" search returns whichever review sites rank that day, so a rating shows up in
one report and is missing from the next, and the trend charts have gaps. Instead each company gets
one product page per tracked site. The page is found once, kept only if it names the company, and
saved; every run after that re-reads exactly those pages.

Which sites are tracked, and why G2 and Capterra are not, is in domain/review_sites.py.

To correct a wrong page, edit or delete review_pages/<company-slug>.json in the store."""
from __future__ import annotations

import logging
import re
from datetime import date

from .config import Company
from .domain.review_sites import TRACKED_SITES, ReviewSite
from .search import SearchProvider
from .store import Store

log = logging.getLogger(__name__)


def pins_key(c: Company) -> str:
    return f"review_pages/{c.slug}.json"


COMPARISON = re.compile(r"/(vs|compare)/", re.I)  # "Paycom vs WebPay" pages name two products


def _candidates(c: Company, site: ReviewSite, search: SearchProvider, limit: int = 3) -> list[str]:
    urls = [site.canonical(m) for hit in search.search(site.query.format(name=c.name), [site.domain])
            if not COMPARISON.search(hit.url) and (m := site.page.search(hit.url))]
    if site.guess:
        urls.append(site.guess(c.slug))
    return list(dict.fromkeys(urls))[:limit]


def names_company(c: Company, text: str) -> bool:
    """The page's main heading names the company ("# Paylocity User Reviews"). Mentions further down
    don't count: a rival's review page lists the company among its alternatives."""
    heading = next((line for line in text.splitlines() if line.startswith("# ")), None)
    region = heading if heading is not None else text[:1500]
    return re.search(rf"(?<![\w-]){re.escape(c.name)}(?![\w-])", region, re.I) is not None


def tracked_review_pages(companies: list[Company], search: SearchProvider, store: Store) -> list[tuple[Company, ReviewSite, str, str]]:
    """(company, site, url, page text) for every tracked page that could be read this run.

    A pinned page that fails to load is skipped for this run but stays pinned: review sites
    time out now and then, and re-pinning would let a different product page slip in."""
    pins = {c.name: (store.get_json(pins_key(c)) or {}).get("pages", {}) for c in companies}
    candidates: dict[str, dict[str, list[str]]] = {c.name: {} for c in companies}
    for c in companies:
        for site in TRACKED_SITES:
            if site.label not in pins[c.name] and (urls := _candidates(c, site, search)):
                candidates[c.name][site.label] = urls

    urls = [u for p in pins.values() for u in p.values()]
    urls += [u for p in candidates.values() for us in p.values() for u in us]
    texts = search.extract(list(dict.fromkeys(urls))) if urls else {}

    out = []
    for c in companies:
        new = {}
        for label, urls in candidates[c.name].items():
            if url := next((u for u in urls if texts.get(u) and names_company(c, texts[u])), None):
                new[label] = url
            else:
                log.info("No %s page found for %s (tried %s)", label, c.name, ", ".join(urls))
        if new:
            pins[c.name] = {**pins[c.name], **new}
            store.put_json(pins_key(c), {"company": c.name, "pages": pins[c.name], "updated": date.today().isoformat()})
            log.info("Pinned review pages for %s: %s", c.name, ", ".join(new))
        for site in TRACKED_SITES:
            url = pins[c.name].get(site.label)
            if url and texts.get(url):
                out.append((c, site, url, texts[url]))
            elif url:
                log.warning("Couldn't read %s's %s page this run (%s)", c.name, site.label, url)
    return out
