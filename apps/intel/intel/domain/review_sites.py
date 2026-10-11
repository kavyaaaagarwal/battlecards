"""The review sites tracked for every company, and how to recognise each one's product page. Pure."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ReviewSite:
    label: str                            # shown on charts; also the rating's site name
    domain: str
    query: str                            # how to find the company's page; {name} is filled in
    page: re.Pattern                      # matches any URL on the company's product page
    canonical: Callable[[re.Match], str]  # that page's reviews URL, so every run reads the same one
    guess: Callable[[str], str] | None = None  # URL to try when search finds no page (gets a company slug)


# Capterra is not tracked: Tavily reads its pages only now and then. Software Advice shows the same
# reviews (both are Gartner Digital Markets sites), loads every time, and adds a support sub-rating.
# G2 is not tracked: it blocks automated reading entirely.
TRACKED_SITES = (
    ReviewSite("Software Advice", "softwareadvice.com", "{name} reviews",
               re.compile(r"softwareadvice\.com/([a-z0-9-]+)/([a-z0-9-]+-profile)", re.I),
               lambda m: f"https://www.softwareadvice.com/{m[1]}/{m[2]}/reviews"),
    ReviewSite("TrustRadius", "trustradius.com", "{name} reviews",
               re.compile(r"trustradius\.com/products/([^/?#]+)", re.I),
               lambda m: f"https://www.trustradius.com/products/{m[1]}/reviews"),
    # Search rarely surfaces the vendor page (it finds "X vs Y" compare pages), so fall back to its usual URL
    ReviewSite("Gartner Peer Insights", "gartner.com", "{name} vendor reviews",
               re.compile(r"gartner\.com/reviews/vendor/([^/?#]+)", re.I),
               lambda m: f"https://www.gartner.com/reviews/vendor/{m[1]}",
               guess=lambda slug: f"https://www.gartner.com/reviews/vendor/{slug}"),
)


def tracked_site(url: str) -> ReviewSite | None:
    return next((s for s in TRACKED_SITES if s.page.search(url)), None)
