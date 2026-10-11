from intel.domain.history import build_history, signals


def run(rid, day, ratings, matrix=None, tiers=None, company="Acme", competitors=("Rival",)):
    return {
        "id": rid, "run_date": day, "status": "succeeded", "company": company, "competitors": list(competitors),
        "profiles": {name: {"ratings": [{"site": site, "rating": v, "review_count": n} for site, (v, n) in r.items()],
                            "pricing_tiers": [{"name": k, "price": v} for k, v in (tiers or {}).get(name, {}).items()]}
                     for name, r in ratings.items()},
        "matrix": {"capabilities": [{"name": n, "cells": [{"company": "Acme", "status": a}, {"company": "Rival", "status": b}]}
                                    for n, a, b in matrix or []]},
        "sources": [],
    }


def test_history_is_one_point_per_day_up_to_this_report():
    a = run("a", "2026-10-01", {"Acme": {}, "Rival": {}})
    b = run("b", "2026-10-05", {"Acme": {}, "Rival": {}})
    later = run("c", "2026-10-09", {"Acme": {}, "Rival": {}})
    other = run("d", "2026-10-02", {"Zed": {}}, company="Zed", competitors=())
    pts = build_history([a, later, other, b], b)
    assert [p["run_date"] for p in pts] == ["2026-10-01", "2026-10-05"]


def test_signals_compare_only_what_both_runs_measured():
    old = run("a", "2026-10-01", {"Acme": {"G2": (4.5, 1000)}, "Rival": {"G2": (4.4, 2000), "Capterra": (4.0, None)}},
              matrix=[("Reporting", "full", "partial"), ("SSO", "partial", "partial")],
              tiers={"Rival": {"Growth": "$49/agent/mo"}})
    new = run("b", "2026-10-09", {"Acme": {"G2": (4.5, 1100)}, "Rival": {"G2": (4.2, 2010)}},
              matrix=[("Reporting", "full", "partial"), ("SSO", "partial", "full")],
              tiers={"Rival": {"Growth": "$59/agent/mo"}})
    sig = signals(build_history([old], new), "Acme")
    texts = [(s["company"], s["text"], s["good_for_us"]) for s in sig]
    assert texts[0] == ("Rival", "Growth tier price changed: $49/agent/mo → $59/agent/mo", None)
    assert not any(t.startswith("Capabilities") for _, t, _ in texts)  # category leaders show this; no tally churn
    assert ("Rival", "G2 rating fell 4.4 → 4.2", True) in texts
    assert ("Acme", "+100 reviews on G2 (1,000 → 1,100)", None) in texts
    assert not any("Capterra" in t for _, t, _ in texts)  # missing this run is not a change
    assert not any("2,000 → 2,010" in t for _, t, _ in texts)  # +0.5% is noise
