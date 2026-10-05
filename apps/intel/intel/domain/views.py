"""Chart data for a report: scorecards, rating comparisons, evidence share.

The single implementation of the scoring rules; the web app only draws these numbers."""
from __future__ import annotations

SCORE = {"full": 2, "partial": 1, "none": 0}
STATUS_LABEL = {"full": "Full", "partial": "Partial", "none": "Not offered", "unknown": "Unknown"}


def _origin(src: dict) -> str | None:
    """Vendor name for a vendor-published source, None for independent ones."""
    o = src.get("origin") or "independent"
    return o.split(":", 1)[1] if o.startswith("vendor:") else None


def _card_ids(card: dict) -> list[str]:
    ids = []
    for key in ("where_we_win", "where_we_lose", "landmines", "objections"):
        for x in card.get(key) or []:
            ids += x.get("sources") or []
    if card.get("pricing_comparison"):
        ids += card["pricing_comparison"].get("sources") or []
    ids += [q["source"] for q in card.get("proof_quotes") or []]
    return list(dict.fromkeys(ids))


def build_views(r: dict) -> dict:
    """Pre-computes everything the charts need, so the template only lays things out."""
    by_id = {s["id"]: s for s in r["sources"]}
    us = r["company"]
    profiles = r.get("profiles", {})
    matrix = (r.get("matrix") or {}).get("capabilities") or []
    # A cell backed only by the company's own site is its claim, not independent evidence.
    matrix = [{**cap, "cells": [{**c, "self": bool(c.get("sources")) and all(
        _origin(by_id[i]) == c["company"] for i in c["sources"] if i in by_id)} for c in cap["cells"]]}
        for cap in matrix]

    def ratings_of(name):
        return {x["site"]: x for x in (profiles.get(name) or {}).get("ratings") or []}

    cards = []
    for card in r["battlecards"]:
        them = card["competitor"]
        # Head-to-head capability rows
        rows, tally = [], {"lead": 0, "even": 0, "behind": 0, "unknown": 0}
        for cap in matrix:
            cells = {c["company"]: c for c in cap["cells"]}
            a, b = cells.get(us, {"status": "unknown"}), cells.get(them, {"status": "unknown"})
            if a["status"] == "unknown" and b["status"] == "unknown":
                continue
            if "unknown" in (a["status"], b["status"]):
                verdict = "unknown"
            else:
                diff = SCORE[a["status"]] - SCORE[b["status"]]
                verdict = "lead" if diff > 0 else "behind" if diff < 0 else "even"
            tally[verdict] += 1
            rows.append({"name": cap["name"], "us": a, "them": b, "verdict": verdict})
        known = tally["lead"] + tally["even"] + tally["behind"]

        # Ratings on sites both have, plus sites only one has
        ra, rb = ratings_of(us), ratings_of(them)
        sites = [s for s in dict.fromkeys([*ra, *rb])]
        ratings = [{"site": s, "us": ra.get(s), "them": rb.get(s)} for s in sites]
        vals = [x["rating"] / x.get("out_of", 5) * 5 for x in [*ra.values(), *rb.values()]]
        lo = max(0.0, min(vals) - 0.5) if vals else 0.0
        lo = float(int(lo * 2) / 2)  # snap to .5 so the axis reads cleanly

        ids = _card_ids(card)
        indie = sum(1 for i in ids if i in by_id and not _origin(by_id[i]))
        cards.append({
            "rows": rows, "tally": tally, "known": known,
            "ratings": ratings, "axis_lo": lo,
            "evidence": {"total": len(ids), "independent": indie,
                         "pct": round(100 * indie / len(ids)) if ids else 0},
        })

    # Market overview: ratings table + capability grid for every company
    names = [us, *r["competitors"]]
    all_sites = list(dict.fromkeys(s for n in names for s in ratings_of(n)))
    market_ratings = [{"name": n, "by_site": ratings_of(n)} for n in names]
    return {"cards": cards, "names": names, "sites": all_sites, "market_ratings": market_ratings,
            "matrix": matrix}
