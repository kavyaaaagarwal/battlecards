"""Run-over-run history: the numbers each report measured, by date, and what moved between them.

Signals are computed from numbers that were verified in each run (ratings checked against review
pages, published price tiers) - not written by a model - so they are the
trustworthy half of "what changed". A value missing from one run is never treated as a change:
search results vary run to run, so absence is not evidence."""
from __future__ import annotations

from .views import SCORE

RATING_STEP = 0.1     # on a 0-5 scale; smaller moves are rounding noise
REVIEW_GROWTH = 0.05  # +5% reviews on a site is worth mentioning


def _scorecard(doc: dict, them: str) -> dict | None:
    us = doc["company"]
    tally, known = {"lead": 0, "even": 0, "behind": 0}, 0
    for cap in (doc.get("matrix") or {}).get("capabilities") or []:
        cells = {c["company"]: c.get("status", "unknown") for c in cap.get("cells") or []}
        a, b = cells.get(us, "unknown"), cells.get(them, "unknown")
        if "unknown" in (a, b):
            continue
        d = SCORE[a] - SCORE[b]
        tally["lead" if d > 0 else "behind" if d < 0 else "even"] += 1
        known += 1
    return {**tally, "known": known} if known else None


def metrics(doc: dict) -> dict:
    """The comparable numbers one run measured, per company."""
    companies = {}
    for name in [doc["company"], *doc.get("competitors", [])]:
        p = (doc.get("profiles") or {}).get(name) or {}
        ratings = {}
        for r in p.get("ratings") or []:
            out_of = r.get("out_of") or 5
            ratings[r["site"]] = {"rating": r["rating"], "out_of": out_of, "rating5": round(r["rating"] / out_of * 5, 2),
                                  "review_count": r.get("review_count")}
        own = [s for s in doc.get("sources") or [] if s.get("company") == name]
        companies[name] = {
            "ratings": ratings,
            "tiers": {t["name"]: t["price"] for t in p.get("pricing_tiers") or []},
            "scorecard": _scorecard(doc, name) if name != doc["company"] else None,
            "sources": len(own),
            "independent": sum(1 for s in own if (s.get("origin") or "independent") == "independent"),
        }
    return {"run_id": doc["id"], "run_date": doc["run_date"], "companies": companies}


def build_history(docs: list[dict], current: dict) -> list[dict]:
    """Finished runs for the same company up to this one, oldest first; one per day (the latest)."""
    name = current["company"].lower()
    same = [d for d in docs if d.get("company", "").lower() == name and d.get("status") in ("succeeded", "partial")
            and d.get("run_date", "") <= current["run_date"] and d.get("id") != current["id"]]
    by_day = {}
    for d in sorted(same, key=lambda d: (d["run_date"], d.get("created_at", ""))):
        by_day[d["run_date"]] = d
    by_day[current["run_date"]] = current
    return [metrics(d) for _, d in sorted(by_day.items())]


def _num(x: float) -> str:
    return f"{x:g}"


def signals(history: list[dict], us: str) -> list[dict]:
    """What moved between the latest run and the most recent earlier run that measured the same thing."""
    if len(history) < 2:
        return []
    latest, earlier = history[-1], history[:-1]
    out = []

    def prev_with(company: str, pick):
        for h in reversed(earlier):
            v = pick(h["companies"].get(company) or {})
            if v is not None:
                return h["run_date"], v
        return None, None

    for company, now in latest["companies"].items():
        ours = company == us
        for site, r in now["ratings"].items():
            when, old = prev_with(company, lambda c, s=site: (c.get("ratings") or {}).get(s))
            if not old:
                continue
            delta = r["rating5"] - old["rating5"]
            if abs(delta) >= RATING_STEP:
                up = delta > 0
                out.append({"company": company, "kind": "rating", "since": when,
                            "text": f"{site} rating {'rose' if up else 'fell'} {_num(old['rating'])} → {_num(r['rating'])}"
                                    + (f"/{_num(r['out_of'])}" if r["out_of"] != 5 else ""),
                            "good_for_us": up if ours else not up, "size": abs(delta)})
            a, b = old.get("review_count"), r.get("review_count")
            if a and b and (b - a) / a >= REVIEW_GROWTH:
                out.append({"company": company, "kind": "reviews", "since": when,
                            "text": f"+{b - a:,} reviews on {site} ({a:,} → {b:,})", "good_for_us": None,
                            "size": (b - a) / a})
        when, old = prev_with(company, lambda c: c.get("tiers") or None)
        for tier, price in (now.get("tiers") or {}).items():
            if old and tier in old and old[tier] != price:
                out.append({"company": company, "kind": "pricing", "since": when,
                            "text": f"{tier} tier price changed: {old[tier]} → {price}", "good_for_us": None, "size": 2.0})
    # Pricing moves first, then the biggest rating moves. Capability-tally moves aren't signals:
    # the overview already shows who leads each category, and a re-worded matrix shifts the tally.
    rank = {"pricing": 0, "rating": 1, "reviews": 2}
    return sorted(out, key=lambda s: (rank[s["kind"]], -s["size"]))


def signals_block(sig: list[dict]) -> str:
    """Signals as plain lines, for the change-report prompt."""
    return "\n".join(f"- {s['company']}: {s['text']} (since {s['since']})" for s in sig) or "(none measured)"
