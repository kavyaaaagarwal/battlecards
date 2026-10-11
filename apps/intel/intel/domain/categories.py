"""Standard buying categories, and who leads each one.

Every report, in any industry, is scored on the same seven categories so the overview can say
"Paylocity leads market voice, Paycor leads pricing" without depending on how a model happened to
name its capabilities. Matrix rows carry a category (asked of the model, keyword-matched for older
runs). The two review categories come from verified review-site ratings, never from the model:

- Rating: are customers happy? Compared only site by site, each rating pulled toward that site's
  average by as many "average reviews" as a typical company there has. 4.5 stars from 31 reviews
  is unproven and lands near average; 4.05 from 2,800 reviews stands.
- Market voice: how many customers are talking? Total reviews, on a log scale (10x the reviews is
  one step up), because a $200k buyer reads 2,800 reviews as "safe choice".

Scores are 0..1 per company per category, and an edge is (them - us) in -1..1: positive means the
competitor is ahead. A category with no evidence is None - never a guess."""
from __future__ import annotations

import math
import re
from statistics import median

CATEGORIES = [
    ("product", "Product"),
    ("pricing", "Pricing & value"),
    ("support", "Support"),
    ("implementation", "Implementation"),
    ("integrations", "Integrations & IT"),
    ("rating", "Rating"),
    ("voice", "Market voice"),
]
IDS = {c for c, _ in CATEGORIES}
REVIEW_CATS = {"rating", "voice"}

# First match wins, so the more specific buyer concerns come before the catch-alls.
_RULES = [
    ("product", r"usability|ease of use|easy to use|interface|\bux\b|\bui\b|mobile app"),
    ("pricing", r"pric|cost|fee|\bcheap|expensive|budget|contract|renewal|discount|\bvalue\b|\broi\b|\btco\b|per (?:user|seat|employee|agent)|billing terms|hidden charge"),
    ("implementation", r"implement|go-?live|migrat|deploy|set-?up|time.to.value|switching|rollout|ramp-?up|data conversion|professional services"),
    ("support", r"support|customer service|service team|account (?:manag|rep)|\bcsm\b|response time|responsive|ticket|help ?desk|escalat|ownership of issues"),
    ("integrations", r"integrations?\b|\bapis?\b|\bsso\b|security|complian|\bsoc ?2|gdpr|hipaa|iso 27001|ecosystem|marketplace|connector|partner network|data residency|\bit team"),
    ("voice", r"market leader|market share|customer base|review (?:base|volume|count)|larger|bigger|established|\bsize\b|\bscale\b|brand|analyst|forrester|\bidc\b|stability|financial|funding|acquisition|acquired|layoff"),
    ("rating", r"\bratings?\b|\brated\b|reputation|\bscores?\b|reviewers? (?:rate|love|praise)|stars?\b|g2|capterra|trustradius|gartner"),
]
_COMPILED = [(cat, re.compile(rx, re.I)) for cat, rx in _RULES]

VALUE = {"full": 1.0, "partial": 0.5, "none": 0.0}
RATING_SPAN = 0.5   # half a star apart (after the pull to average) is a full-strength edge
MISSING_COUNT = 10  # a rating with no stated review count is treated as a small sample
THIN = 50           # under this many reviews in total, a company's rating is low confidence


def classify(text: str) -> str:
    """The standard category a capability or talk-track point is about."""
    for cat, rx in _COMPILED:
        if rx.search(text or ""):
            return cat
    return "product"


def category_of(cap: dict) -> str:
    c = cap.get("category")
    if c == "reputation":  # older tag, before reputation was split in two
        return "voice"
    return c if c in IDS else classify(cap.get("name", ""))


def _r5(r: dict) -> float:
    return r["rating"] / (r.get("out_of") or 5) * 5


def _count(r: dict) -> int:
    return r.get("review_count") or MISSING_COUNT


def _fair_ratings(names: list[str], ratings_of) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    """Each company's rating on each site after the pull to that site's average, and each site's
    average. The pull is the site's median review count in "average reviews": a company with far
    fewer real reviews than that is mostly average; one with far more barely moves."""
    fair: dict[str, dict[str, float]] = {n: {} for n in names}
    prior: dict[str, float] = {}
    for site in dict.fromkeys(s for n in names for s in ratings_of(n)):
        rs = {n: ratings_of(n)[site] for n in names if site in ratings_of(n)}
        k = {n: _count(r) for n, r in rs.items()}
        avg = sum(_r5(r) * k[n] for n, r in rs.items()) / sum(k.values())
        m = median(k.values())
        prior[site] = avg
        for n, r in rs.items():
            fair[n][site] = (_r5(r) * k[n] + avg * m) / (k[n] + m)
    return fair, prior


def _rating_detail(name: str, ratings_of) -> str:
    parts = []
    for site, r in ratings_of(name).items():
        scale = f"/{r['out_of']:g}" if (r.get("out_of") or 5) != 5 else ""
        n = f" ({r['review_count']:,} reviews)" if r.get("review_count") else " (review count not stated)"
        parts.append(f"{site} {r['rating']:g}{scale}{n}")
    return " · ".join(parts)


def _reviews(name: str, ratings_of) -> int:
    return sum(r.get("review_count") or 0 for r in ratings_of(name).values())


def _review_categories(us: str, names: list[str], ratings_of, edges: dict) -> list[dict]:
    fair, prior = _fair_ratings(names, ratings_of)
    rated = [n for n in names if fair[n]]
    overall = (sum(prior.values()) / len(prior)) if prior else 0
    thin = [n for n in rated if _reviews(n, ratings_of) < THIN]

    # Rating: how far above or below each site's average, averaged over the sites a company is on
    rel = {n: sum(fair[n][s] - prior[s] for s in fair[n]) / len(fair[n]) for n in rated}
    rating = {
        "scores": {n: round(max(0, min(1, 0.5 + rel[n] / (2 * RATING_SPAN))), 3) if n in rel else None for n in names},
        "values": {n: round(overall + rel[n], 2) if n in rel else None for n in names},
        "detail": {n: _rating_detail(n, ratings_of) for n in names},
        "basis": f"{len(prior)} review site{'s' if len(prior) != 1 else ''}, compared site by site",
        "thin": thin,
    }
    for them in edges:
        shared = [s for s in fair[us] if s in fair[them]]  # never compare across different sites
        edges[them]["rating"] = round(max(-1, min(1, sum(fair[them][s] - fair[us][s] for s in shared)
                                                  / len(shared) / RATING_SPAN)), 3) if shared else None

    # Market voice: total reviews, log scale, biggest company = 1
    total = {n: _reviews(n, ratings_of) for n in names}
    logs = {n: math.log10(1 + t) for n, t in total.items()}
    top = max(logs.values(), default=0)
    voice = {
        "scores": {n: round(logs[n] / top, 3) if top else None for n in names},
        "values": {n: float(total[n]) if top else None for n in names},
        "detail": {n: f"{total[n]:,} reviews across review sites" for n in names},
        "basis": "review volume across review sites",
        "thin": [],
    }
    for them in edges:
        edges[them]["voice"] = round(voice["scores"][them] - voice["scores"][us], 3) if top else None
    return [rating, voice]


def _leader(scores: dict[str, float | None]) -> str | None:
    known = {n: s for n, s in scores.items() if s is not None}
    if len(known) < 2:
        return None
    ranked = sorted(known.items(), key=lambda kv: -kv[1])
    return ranked[0][0] if ranked[0][1] - ranked[1][1] >= 0.05 else None  # a near-tie has no leader


def build_categories(us: str, names: list[str], matrix: list[dict], ratings_of) -> dict:
    """Per-category scores and leaders for every company, plus each competitor's edge over us."""
    by_cat: dict[str, list[dict]] = {c: [] for c in IDS}
    for cap in matrix:
        by_cat[category_of(cap)].append(cap)

    edges: dict[str, dict] = {n: {} for n in names if n != us}
    review = dict(zip(("rating", "voice"), _review_categories(us, names, ratings_of, edges), strict=True))
    cats = []
    for cid, label in CATEGORIES:
        if cid in REVIEW_CATS:
            r = review[cid]
            has = any(v is not None for v in r["scores"].values())
            cats.append({"id": cid, "label": label, "basis": r["basis"] if has else "no evidence",
                         "leader": _leader(r["scores"]), "scores": r["scores"], "detail": r["detail"],
                         "values": r["values"], "thin": r["thin"]})
            continue
        caps = by_cat[cid]
        scores: dict[str, float | None] = {}
        detail: dict[str, str] = {}
        for n in names:
            cells = [(cap["name"], c) for cap in caps for c in cap["cells"] if c["company"] == n]
            known = [VALUE[c["status"]] for _, c in cells if c["status"] in VALUE]
            scores[n] = round(sum(known) / len(known), 3) if known else None
            detail[n] = " · ".join(f"{name}: {c['status']}" for name, c in cells if c["status"] in VALUE)
        for them in edges:
            pairs = []
            for cap in caps:
                cells = {c["company"]: c["status"] for c in cap["cells"]}
                a, b = cells.get(us, "unknown"), cells.get(them, "unknown")
                if a in VALUE and b in VALUE:
                    pairs.append(VALUE[b] - VALUE[a])
            edges[them][cid] = round(sum(pairs) / len(pairs), 3) if pairs else None
        cats.append({"id": cid, "label": label, "leader": _leader(scores), "scores": scores, "detail": detail,
                     "basis": f"{len(caps)} capabilit{'y' if len(caps) == 1 else 'ies'}" if caps else "no evidence",
                     "values": {}, "thin": []})

    return {"categories": cats, "edges": edges}


def point_tags(card: dict) -> dict[str, list[str]]:
    """The category each talk-track point is about, index-aligned with the card's lists, so the
    web app can bring the points that matter for a deal to the top. Only the headline (or the
    question) decides: supporting text mentions "support" and "reviews" too often to be a signal."""
    return {
        "wins": [classify(x.get("headline", "")) for x in card.get("where_we_win") or []],
        "losses": [classify(x.get("headline", "")) for x in card.get("where_we_lose") or []],
        "asks": [classify(x.get("question", "")) for x in card.get("landmines") or []],
        "objections": [classify(x.get("objection", "")) for x in card.get("objections") or []],
    }
