"""Shared offline fakes: a fake search provider and a fake LLM, so tests need no API keys."""
from __future__ import annotations

import pytest

from intel.search import SearchHit, SearchProvider
from intel.stages import Deps
from intel.store import MemoryStore

REVIEW = (
    "I've used Acme Desk for two years. Honestly the reporting is painful and we had to export "
    "everything to spreadsheets just to see first response time by team. Setup took a single afternoon though."
)
PRICING = "Acme Desk pricing: Starter $19 per agent/month. Growth $49 per agent/month. Enterprise: contact sales."


# ── end-to-end with fakes ───────────────────────────────────
class FakeSearch(SearchProvider):
    name = "fake"

    def _search(self, query, include_domains, news_days, exclude_domains=None):
        company = query.split()[0]
        if "official website" in query:
            return [SearchHit(f"https://{company.lower()}.com", company, f"{company} official site")]
        host = f"{company.lower()}.com"
        if "pricing" in query:
            text = PRICING.replace("Acme Desk", company)
        elif "reviews" in query:
            text = REVIEW.replace("Acme Desk", company) + " Rated 4.6 out of 5 from 1,320 reviews."
            host = "g2.com"
        else:
            text = f"{company} is the AI-first help desk for growing teams. {query}. " * 3
        if exclude_domains:  # independent comparisons / round-ups
            host = "independent-reviews.net"
        return [SearchHit(f"https://{host}/{abs(hash(query)) % 9999}", query, text)]


class FakeLLM:
    """Returns schema-valid objects that cite the source IDs it was shown."""

    calls: list[str] = []  # schema names, across all instances; reset per test
    fail_for: set[str] = set()  # company names whose CompanyProfile call raises once

    def __init__(self, cfg):
        self.model, self.provider = "fake-model", "fake"
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def structured(self, system, prompt, schema, max_tokens=8000):
        import re

        FakeLLM.calls.append(schema.__name__)
        for name in list(FakeLLM.fail_for):
            if schema.__name__ == "CompanyProfile" and f"**{name}**" in prompt:
                FakeLLM.fail_for.discard(name)
                raise RuntimeError(f"flaky model for {name}")
        self.usage["calls"] += 1
        ids = re.findall(r"\[(S\d+)\] \((\w+)", prompt) or [(i, "") for i in re.findall(r'"(S\d+)"', prompt)]
        first = ids[0][0] if ids else "S1"
        review_id = next((i for i, cat in ids if cat == "reviews"), first)
        name = schema.__name__
        if name == "CompanyProfile":
            return schema(
                name="?",
                positioning={"text": "AI-first help desk for growing teams", "sources": [first]},
                key_capabilities=[{"text": "Fast setup", "sources": [review_id]}, {"text": "Invented", "sources": []}],
                pricing_tiers=[{"name": "Growth", "price": "$49 per agent/month", "sources": [first]}],
                review_weaknesses=[{"text": "Reporting requires spreadsheet exports", "sources": [review_id]}],
                ratings=[{"site": "G2", "rating": 4.6, "review_count": 1320, "source": review_id},
                         {"site": "Capterra", "rating": 4.9, "source": review_id}],  # 4.9 isn't in the source
                quotes=[
                    {"quote": "the reporting is painful and we had to export everything to spreadsheets",
                     "sentiment": "pain", "source": review_id},
                    {"quote": "This is a hallucinated quote", "sentiment": "praise", "source": review_id},
                ],
            )
        if name == "Battlecard":
            return schema(
                competitor="?",
                tldr="We win on setup speed. We lose on brand.",
                overview="Rival sells help desk software to enterprises.",
                quick_dismiss="Rival is a solid enterprise pick, but setup takes months. We are live in an afternoon.",
                where_we_win=[{"headline": "Setup in an afternoon", "detail": "No consultants needed.", "sources": [first]}],
                where_we_lose=[{"headline": "Brand recognition", "counter": "Ask for a reference in their segment", "sources": [first]}],
                landmines=[{"question": "How do you report on FRT by team?", "why": "Needs exports", "sources": [first]}],
                objections=[{"objection": "They're the market leader", "response": "Leader ≠ fit", "sources": [first]}],
            )
        if name == "CapabilityMatrix":
            return schema(capabilities=[
                {"name": "Reporting", "cells": [
                    {"company": "Acme", "status": "full", "sources": [first]},
                    {"company": "Rival", "status": "partial", "note": "Exports only", "sources": [review_id]},
                    {"company": "Other", "status": "none", "sources": []},  # no evidence -> unknown
                ]},
                {"name": "Telepathy", "cells": []},  # nothing known -> row dropped
            ])
        if name == "PositioningAnalysis":
            return schema(
                table_stakes=[{"theme": "AI-first", "companies": ["Acme", "Rival"], "sources": [first]}],
                white_space=[{"opportunity": "Reporting without spreadsheets", "evidence": "Reviews", "sources": [first]}],
                recommended_angle={"text": "Own 'answers without exports'", "sources": [first]},
            )
        if name == "ChangeReport":
            return schema(changes=[{"company": "Rival", "change": "New Growth tier", "why_it_matters": "Undercuts us",
                                    "severity": "high", "sources": [first]}])
        raise AssertionError(name)


FAKE_DEPS = Deps(make_search=lambda cfg, cache: FakeSearch(cache, 3), make_llm=FakeLLM)


@pytest.fixture
def offline(monkeypatch):
    """No network: page fetches and keyless APIs return nothing."""
    monkeypatch.setattr("intel.collect.fetch_page", lambda url, cache: "")
    monkeypatch.setattr("intel.collect.fetch_json", lambda url, cache, params=None: None)


@pytest.fixture
def store():
    FakeLLM.calls.clear()
    FakeLLM.fail_for.clear()
    return MemoryStore()
