"""Review-site ratings are numbers: keep only ones printed on an independent review page."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..models import Rating, Source

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
        if not src or src.vendor or not urlparse(src.url).netloc.lower().removeprefix("www.").endswith(REVIEW_DOMAINS):
            continue
        if not (0 < r.rating <= r.out_of) or not number_in_text(r.rating, src.content):
            continue
        if r.review_count is not None and not number_in_text(r.review_count, src.content):
            r.review_count = None
        if all(k.site.lower() != r.site.lower() for k in kept):
            kept.append(r)
    return kept
