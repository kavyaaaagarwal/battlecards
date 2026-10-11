"""Review-site ratings are numbers: keep only ones printed on a tracked review page.

Only the fixed pages in review_pages.py count, so each run measures the same pages and the
trend charts compare like with like. The site name comes from the URL, not the model, so
"G2" and "G2.com" can't split one site into two chart lines."""
from __future__ import annotations

import re

from ..models import Rating, Source
from .review_sites import tracked_site

REVIEW_DOMAINS = ("g2.com", "capterra.com", "trustradius.com", "gartner.com", "getapp.com",
                  "softwareadvice.com", "trustpilot.com", "peerspot.com")


def number_in_text(value: float | int, text: str) -> bool:
    """True if the number appears in the text as written (4.5, 4.50, 1,320, 1320)."""
    if isinstance(value, float) and not value.is_integer():
        pats = [re.escape(f"{value:g}"), re.escape(f"{value:.2f}")]
    else:
        n = int(value)
        pats = [re.escape(f"{n:,}"), re.escape(str(n))]
    return any(re.search(rf"(?<![\d.,]){p}(?![\d])", text) for p in pats)


def verify_ratings(ratings: list[Rating], by_id: dict[str, Source]) -> list[Rating]:
    kept: list[Rating] = []
    for r in ratings:
        src = by_id.get(r.source)
        site = tracked_site(src.url) if src and not src.vendor else None
        if not site:
            continue
        r.site = site.label
        if not (0 < r.rating <= r.out_of) or not number_in_text(r.rating, src.content):
            continue
        if r.review_count is not None and not number_in_text(r.review_count, src.content):
            r.review_count = None
        if all(k.site.lower() != r.site.lower() for k in kept):
            kept.append(r)
    return kept
