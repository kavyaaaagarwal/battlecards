"""Who published a source: a company (vendor) or someone independent."""
from __future__ import annotations

from urllib.parse import urlparse

from ..config import Company
from ..models import Source

# Press-release wires carry the company's own words, so they count as vendor sources.
NEWSWIRES = ["prnewswire.com", "globenewswire.com", "businesswire.com", "accessnewswire.com", "einpresswire.com"]
MARKET = "_market"


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def classify_origin(url: str, query_company: str, companies: list[Company]) -> str:
    d = _domain(url)
    for c in companies:
        if c.domain and (d == c.domain or d.endswith("." + c.domain)):
            return f"vendor:{c.name}"
    if any(d.endswith(w) for w in NEWSWIRES) and query_company != MARKET:
        return f"vendor:{query_company}"
    return "independent"


def origin_label(s: Source) -> str:
    return f"BY {s.vendor}" if s.vendor else "INDEPENDENT"
