from intel.domain.views import build_views


def doc(**over):
    base = {
        "company": "Acme", "competitors": ["Rival"],
        "sources": [
            {"id": "S1", "origin": "independent"},
            {"id": "S2", "origin": "vendor:Acme"},
        ],
        "profiles": {}, "matrix": None,
        "battlecards": [{
            "competitor": "Rival",
            "where_we_win": [{"headline": "x", "sources": ["S1", "S2"]}],
            "where_we_lose": [], "landmines": [], "objections": [], "proof_quotes": [],
        }],
    }
    base.update(over)
    return base


def test_evidence_pct_counts_unique_independent_sources():
    ev = build_views(doc())["cards"][0]["evidence"]
    assert ev == {"total": 2, "independent": 1, "pct": 50}


def test_scorecard_excludes_unknown_and_flags_self_reported():
    matrix = {"capabilities": [
        {"name": "A", "cells": [{"company": "Acme", "status": "full", "sources": ["S2"]},
                                {"company": "Rival", "status": "partial", "sources": ["S1"]}]},
        {"name": "B", "cells": [{"company": "Acme", "status": "full", "sources": ["S1"]},
                                {"company": "Rival", "status": "unknown", "sources": []}]},
        {"name": "C", "cells": [{"company": "Acme", "status": "none", "sources": ["S1"]},
                                {"company": "Rival", "status": "full", "sources": ["S1"]}]},
    ]}
    card = build_views(doc(matrix=matrix))["cards"][0]
    assert card["tally"] == {"lead": 1, "even": 0, "behind": 1, "unknown": 1}
    assert card["known"] == 2
    assert card["rows"][0]["us"]["self"] is True   # only Acme's own site
    assert card["rows"][1]["us"]["self"] is False  # independent source


def test_views_without_matrix_or_ratings():
    v = build_views(doc(battlecards=[{"competitor": "Rival"}]))
    assert v["cards"][0]["rows"] == [] and v["cards"][0]["ratings"] == []
    assert v["cards"][0]["evidence"]["pct"] == 0 and v["matrix"] == [] and v["sites"] == []
