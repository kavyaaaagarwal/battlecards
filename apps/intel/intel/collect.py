"""Turns company names into a pool of cited web sources.

The query plan is generic: nothing here is specific to any company or market,
so swapping names in .env is all it takes to point the agent somewhere new."""
from __future__ import annotations

import logging
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from .cache import DiskCache
from .config import Company, Config, slugify
from .domain.origins import MARKET, NEWSWIRES, classify_origin  # noqa: F401
from .models import Source
from .search import SearchHit, SearchProvider, domain_of, fetch_page

log = logging.getLogger(__name__)

REVIEW_SITES = [
    "g2.com", "capterra.com", "trustradius.com", "gartner.com", "getapp.com",
    "softwareadvice.com", "trustpilot.com", "peerspot.com",
]
COMMUNITY_SITES = ["reddit.com", "news.ycombinator.com", "quora.com"]

# Never treat these as a company's official site during auto-discovery
NOT_OFFICIAL = {
    "wikipedia.org", "linkedin.com", "crunchbase.com", "g2.com", "capterra.com",
    "trustradius.com", "reddit.com", "youtube.com", "twitter.com", "x.com",
    "facebook.com", "instagram.com", "glassdoor.com", "bloomberg.com", "forbes.com",
    "techcrunch.com", "medium.com", "gartner.com", "getapp.com", "softwareadvice.com",
    "producthunt.com", "apps.apple.com", "play.google.com", "github.com", "zoominfo.com",
}


@dataclass
class Query:
    company: str
    category: str
    text: str
    include_domains: list[str] | None = None
    news_days: int | None = None
    exclude_domains: list[str] | None = None


def plan_queries(c: Company, category_hint: str, vendor_domains: list[str]) -> list[Query]:
    """What a company says (its own site) + what everyone else says (reviews, forums,
    independent comparisons). Independent queries exclude every vendor's site so a
    rival's "X vs Y" blog post can't masquerade as neutral evidence."""
    n, h = c.name, category_hint
    own = [c.domain] if c.domain else None
    indie = vendor_domains or None
    return [
        # What they say
        Query(n, "positioning", f"{n} {h} platform overview what is {n}".strip(), own),
        Query(n, "pricing", f"{n} pricing plans per month", own),
        # What others say (news also covers launches; reviews also carry star ratings)
        Query(n, "news", f"{n} launches announces new", news_days=120),
        Query(n, "reviews", f"{n} {h} reviews rating pros and cons".strip(), REVIEW_SITES),
        Query(n, "complaints", f"{n} complaints problems honest experience", REVIEW_SITES + COMMUNITY_SITES),
        Query(n, "alternatives", f"{n} alternatives competitors {h}".strip(), exclude_domains=indie),
    ]


def plan_comparison_queries(company: Company, competitors: list[Company], vendor_domains: list[str]) -> list[Query]:
    return [
        Query(comp.name, "comparison", f"{company.name} vs {comp.name}", exclude_domains=vendor_domains or None)
        for comp in competitors
    ]


def plan_market_queries(category_hint: str, vendor_domains: list[str]) -> list[Query]:
    """Independent round-ups of the whole category - used for the capability matrix."""
    if not category_hint:
        return []
    return [Query(MARKET, "market", f"best {category_hint} comparison features", exclude_domains=vendor_domains or None)]




# ── Free, keyless data sources ──────────────────────────────
WIKI_UA = {"User-Agent": "competitive-intel-agent/1.0 (open-source research tool)"}


def fetch_json(url: str, cache: DiskCache, params: dict | None = None):
    """GET a JSON API through the cache. Returns None on any failure."""
    import requests

    def _get():

        for attempt in range(3):
            try:
                r = requests.get(url, params=params, headers=WIKI_UA, timeout=15)
                if r.status_code in (429, 503):  # public APIs throttle bursts - back off and retry
                    time.sleep(2 * (attempt + 1))
                    continue
                return r.json() if r.ok else None
            except (requests.RequestException, ValueError) as e:
                log.debug("fetch_json failed %s: %s", url, e)
                return None
        log.debug("fetch_json gave up (rate limited) %s", url)
        return None

    return cache.get_or_set("api", {"u": url, "p": params}, _get)


def _wikidata_value(claims: dict, prop: str):
    """The current value of a property: the 'preferred' statement, else the latest dated one."""
    stmts = [x for x in claims.get(prop, []) if x.get("mainsnak", {}).get("datavalue") and x.get("rank") != "deprecated"]
    if not stmts:
        return None

    def when(x):
        q = x.get("qualifiers", {}).get("P585") or [{}]
        return (q[0].get("datavalue") or {}).get("value", {}).get("time", "")

    best = max(stmts, key=lambda x: (x.get("rank") == "preferred", when(x)))
    return best["mainsnak"]["datavalue"]["value"]


def wikipedia_facts(c: Company, cache: DiskCache) -> tuple[dict, Source | None]:
    """Founded / HQ / employees / owner from Wikipedia + Wikidata. Only accepted when the
    page clearly is this company (official website matches, or the name matches and the
    page describes a company) - a wrong page is worse than none."""
    token = slugify(c.name)

    def same_name(title: str) -> bool:  # "Paycor" must not match "Paycor Stadium"
        return re.sub(r"-(company|software|inc)$", "", slugify(title)) == token

    def summary(title: str):
        d = fetch_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}", cache)
        # Redirects are followed - only keep them when they land on the same name
        return d if d and d.get("type") == "standard" and same_name(d.get("title", "")) else None

    summ = summary(c.name) or summary(f"{c.name} (company)")
    if not summ:
        res = fetch_json("https://en.wikipedia.org/w/api.php", cache, {
            "action": "query", "list": "search", "srsearch": c.name, "format": "json", "srlimit": 5})
        title = next((h["title"] for h in (res or {}).get("query", {}).get("search", []) if same_name(h["title"])), None)
        summ = summary(title) if title else None
    if not summ:
        return {}, None
    title = summ["title"]
    qid = summ.get("wikibase_item")
    ent = fetch_json("https://www.wikidata.org/wiki/Special:EntityData/%s.json" % qid, cache) if qid else None
    claims = ((ent or {}).get("entities", {}).get(qid, {}) or {}).get("claims", {})

    site = _wikidata_value(claims, "P856")
    site_domain = domain_of(site) if isinstance(site, str) else None
    looks_like_company = re.search(r"\b(company|corporation|provider|software|firm|inc\.?)\b",
                                   (summ.get("description") or "") + " " + summ.get("extract", ""), re.I)
    if c.domain and site_domain and not site_domain.endswith(c.domain):
        return {}, None  # different organisation with a similar name
    if not (c.domain and site_domain) and not looks_like_company:
        return {}, None

    facts: dict = {"wikipedia": summ.get("content_urls", {}).get("desktop", {}).get("page")}
    inception = _wikidata_value(claims, "P571")
    if isinstance(inception, dict) and inception.get("time"):
        facts["founded"] = inception["time"].lstrip("+")[:4]
    employees = _wikidata_value(claims, "P1128")
    if isinstance(employees, dict) and employees.get("amount"):
        facts["employees"] = f"{int(float(employees['amount'])):,}"
    label_ids = {k: v["id"] for k in ("P159", "P749", "P127")
                 if isinstance(v := _wikidata_value(claims, k), dict) and "id" in v}
    if label_ids:
        lab = fetch_json("https://www.wikidata.org/w/api.php", cache, {
            "action": "wbgetentities", "ids": "|".join(label_ids.values()), "props": "labels",
            "languages": "en", "format": "json"})
        names = {i: e.get("labels", {}).get("en", {}).get("value") for i, e in (lab or {}).get("entities", {}).items()}
        if names.get(label_ids.get("P159")):
            facts["headquarters"] = names[label_ids["P159"]]
        owner = names.get(label_ids.get("P749")) or names.get(label_ids.get("P127"))
        if owner:
            facts["owner"] = owner

    fact_line = "; ".join(f"{k}: {v}" for k, v in facts.items() if k != "wikipedia")
    content = f"{summ.get('extract', '')}\n\nWikidata facts - {fact_line}" if fact_line else summ.get("extract", "")
    src = Source(id="", company=c.name, category="company_facts", url=facts["wikipedia"] or "",
                 title=f"{title} - Wikipedia", content=content)
    return facts, src


def hacker_news(c: Company, cache: DiskCache, limit: int = 3) -> list[Source]:
    """Developer/operator chatter from Hacker News (Algolia API, free)."""
    res = fetch_json("https://hn.algolia.com/api/v1/search", cache,
                     {"query": f'"{c.name}"', "tags": "comment", "hitsPerPage": 20})
    out = []
    word = re.compile(rf"\b{re.escape(c.name)}\b", re.I)
    for h in (res or {}).get("hits", []):
        text = re.sub(r"<[^>]+>", " ", h.get("comment_text") or "")
        text = re.sub(r"&#x27;", "'", re.sub(r"&quot;", '"', re.sub(r"&amp;", "&", text)))
        if len(text) < 200 or not word.search(text):
            continue
        out.append(Source(id="", company=c.name, category="community",
                          url=f"https://news.ycombinator.com/item?id={h['objectID']}",
                          title=f"Hacker News comment on {c.name}", content=text,
                          published=(h.get("created_at") or "")[:10] or None))
        if len(out) >= limit:
            break
    return out


def is_about(c: Company, url: str, title: str, content: str) -> bool:
    """A source counts for a company only if it's on the company's own site or names it.
    Stops a vague search ("Acme reviews") from filing a page about someone else under Acme."""
    if c.domain and domain_of(url).endswith(c.domain):
        return True
    return re.search(rf"(?<![\w-]){re.escape(c.name)}(?![\w-])", f"{title}\n{content}", re.I) is not None


def discover_domain(c: Company, category_hint: str, search: SearchProvider) -> str | None:
    """Find a company's official domain when it isn't pinned in .env."""
    hits = search.search(f"{c.name} {category_hint} official website".strip())
    token = slugify(c.name).replace("-", "")
    # Only accept a domain that contains the company's name (paylocity -> paylocity.com,
    # isolved -> isolvedhcm.com). A wrong domain is worse than none: it would scope the
    # company's own pricing/positioning searches to someone else's site (e.g. a news site).
    for hit in hits:
        d = domain_of(hit.url)
        root = ".".join(d.split(".")[-2:])
        if root in NOT_OFFICIAL:
            continue
        if token and token in root.replace("-", "").replace(".", ""):
            return root
    log.warning(
        "Couldn't confidently find %s's website - pin it in .env, e.g. COMPETITORS=%s:example.com",
        c.name, c.name,
    )
    return None


def normalize_url(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc.lower().removeprefix("www."), p.path.rstrip("/"), "", "", ""))


def clean_text(text: str, limit: int) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)          # markdown images
    text = re.sub(r"\[([^\]]+)\]\((?:[^)]*)\)", r"\1", text)  # keep link text only
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit]


def collect_sources(cfg: Config, search: SearchProvider, cache: DiskCache, *, deadline: float | None = None,
                    stats: dict | None = None) -> tuple[list[Source], dict]:
    """deadline (time.monotonic()): stop starting searches when it passes and keep what has finished,
    so a slow search provider can't push the stage past the serverless time limit."""
    # 1. Resolve official domains
    for c in cfg.all_companies:
        if not c.domain:
            c.domain = discover_domain(c, cfg.category, search)
            log.info("Discovered domain for %s: %s", c.name, c.domain or "(not found)")

    # 2. Build the plan
    vendor_domains = [c.domain for c in cfg.all_companies if c.domain]
    queries: list[Query] = []
    for c in cfg.all_companies:
        queries += plan_queries(c, cfg.category, vendor_domains)
    queries += plan_comparison_queries(cfg.company, cfg.competitors, vendor_domains)
    queries += plan_market_queries(cfg.category, vendor_domains)

    # 3. Run it (DDG rate-limits aggressively, so be gentler there)
    workers = 4 if search.name == "tavily" else 2
    pool = ThreadPoolExecutor(max_workers=workers)
    futures = {pool.submit(search.search, q.text, q.include_domains, q.news_days, q.exclude_domains): q for q in queries}
    results: list[tuple[Query, list[SearchHit]]] = []
    try:
        timeout = None if deadline is None else max(0.0, deadline - time.monotonic())
        for f in as_completed(futures, timeout=timeout):
            results.append((futures[f], f.result()))
    except TimeoutError:
        log.warning("Collection time limit reached: %d of %d searches finished", len(results), len(queries))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)  # don't wait for searches still in flight
    results.sort(key=lambda r: queries.index(r[0]))  # stable source numbering
    if stats is not None:
        stats.update(searches_done=len(results), searches_planned=len(queries))
    out_of_time = deadline is not None and time.monotonic() >= deadline

    # 4. Homepages are fetched directly - free and the most reliable positioning source
    homepages: list[tuple[Query, list[SearchHit]]] = []
    for c in cfg.all_companies:
        if c.domain and not out_of_time:
            url = f"https://{c.domain}"
            text = fetch_page(url, cache)
            if text:
                homepages.append((Query(c.name, "positioning", "homepage"), [SearchHit(url, f"{c.name} homepage", text)]))

    # 4b. Own site not indexed or not reachable? One open search for the company by name instead.
    for c in [] if out_of_time else cfg.all_companies:
        own_pages = any(hits for q, hits in homepages + results
                         if q.company == c.name and (q.text == "homepage" or q.include_domains == [c.domain]))
        if not own_pages:
            text = f'"{c.name}" {cfg.category}'.strip()
            results.append((Query(c.name, "positioning", text), search.search(text)))

    # 5. Free structured sources: Wikipedia/Wikidata facts + Hacker News
    facts: dict[str, dict] = {}
    extra: list[Source] = []
    for c in [] if out_of_time else cfg.all_companies:
        f, wiki = wikipedia_facts(c, cache)
        if f:
            facts[c.name] = f
        extra += ([wiki] if wiki else []) + hacker_news(c, cache)

    # 6. Deduplicate into a numbered source registry
    sources: list[Source] = []
    seen: set[str] = set()
    for src in extra:
        key = normalize_url(src.url)
        if key in seen:
            continue
        seen.add(key)
        sources.append(src.model_copy(update={"id": f"S{len(sources) + 1}",
                                               "content": clean_text(src.content, cfg.max_chars_per_source)}))
    by_name = {c.name: c for c in cfg.all_companies}
    for q, hits in homepages + results:
        for hit in hits:
            key = normalize_url(hit.url)
            content = clean_text(hit.content, cfg.max_chars_per_source)
            if key in seen or len(content) < 80:
                continue
            if q.company in by_name and not is_about(by_name[q.company], hit.url, hit.title, content):
                log.debug("Dropped off-topic source for %s: %s", q.company, hit.url)
                continue
            seen.add(key)
            sources.append(
                Source(
                    id=f"S{len(sources) + 1}",
                    company=q.company,
                    category=q.category,
                    url=hit.url,
                    title=hit.title.strip() or hit.url,
                    content=content,
                    published=hit.published,
                    origin=classify_origin(hit.url, q.company, cfg.all_companies),
                )
            )

    counts = Counter(s.company for s in sources)
    indie = Counter(s.company for s in sources if s.origin == "independent")
    for c in cfg.all_companies:
        log.info("  %-20s %d sources (%d independent)", c.name, counts.get(c.name, 0), indie.get(c.name, 0))
        if counts.get(c.name, 0) < 4:
            log.warning("Few sources for %s - consider pinning its domain or setting CATEGORY.", c.name)
    if counts.get(MARKET):
        log.info("  %-20s %d sources", "(market round-ups)", counts[MARKET])
    return sources, facts
