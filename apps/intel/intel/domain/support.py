"""What kind of page a source is, and how well a claim is backed. Pure rules, no I/O."""
from __future__ import annotations

from urllib.parse import urlparse

from ..models import Source
from .ratings import REVIEW_DOMAINS

COMMUNITY_DOMAINS = ("reddit.com", "news.ycombinator.com", "quora.com", "stackexchange.com", "community.")
REFERENCE_DOMAINS = ("wikipedia.org", "wikidata.org")

# Source kinds, in the order a rep should trust them for claims about customer experience
KIND_LABEL = {
    "review": "Review site", "community": "Forum", "news": "News", "reference": "Reference",
    "analysis": "Third-party article", "vendor": "Vendor's own site",
}


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def source_kind(src: Source | dict) -> str:
    get = src.get if isinstance(src, dict) else lambda k, d=None: getattr(src, k, d)
    origin, host, category = get("origin") or "independent", _host(get("url") or ""), get("category") or ""
    if origin.startswith("vendor:"):
        return "vendor"
    if host.endswith(REVIEW_DOMAINS):
        return "review"
    if host.endswith(REFERENCE_DOMAINS):
        return "reference"
    if any(host.endswith(d) or host.startswith(d) for d in COMMUNITY_DOMAINS) or category == "community":
        return "community"
    if category == "news":
        return "news"
    # "X vs Y" posts and round-ups: independent of the two vendors, but often someone else's marketing
    return "analysis"


def rate_support(evidence_ids: list[str], cited_ids: list[str], by_id: dict[str, Source]) -> str | None:
    """corroborated / single_source / vendor_claim from the sources whose verbatim excerpt
    survived verification; cited_only when no excerpt survived but the citation did."""
    if not evidence_ids:
        return "cited_only" if cited_ids else None
    srcs = [by_id[i] for i in evidence_ids if i in by_id]
    independent = {_host(s.url) for s in srcs if not s.vendor}
    if len(independent) >= 2:
        return "corroborated"
    if independent:
        return "single_source"
    return "vendor_claim"


# Display order: how safely a rep can say it. Ties keep the model's order (it ranks by sales relevance).
SUPPORT_RANK = {"corroborated": 0, "single_source": 1, None: 2, "vendor_claim": 3, "cited_only": 4}


def by_strength(items: list, keep: int = 5) -> list:
    """Strongest-backed first, then cap. Nothing is hidden by this - the UI shows the top 3 and
    puts the rest behind "show more"; the cap only stops a model from padding the list."""
    return sorted(items, key=lambda x: SUPPORT_RANK.get(getattr(x, "support", None), 2))[:keep]
