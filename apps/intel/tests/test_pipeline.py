"""Offline unit tests for parsing, verification and evidence rules.

    pytest -q
"""
from __future__ import annotations

import pytest
from conftest import REVIEW

from intel.config import Company, parse_company
from intel.domain.verify import Verifier, quote_is_verbatim
from intel.llm import extract_json
from intel.models import Claim, CompanyProfile, Quote, Source


# ── unit tests ──────────────────────────────────────────────
def test_parse_company_with_and_without_domain():
    assert parse_company("HubSpot:hubspot.com").domain == "hubspot.com"
    assert parse_company(" Zendesk ").domain is None
    assert parse_company("Acme : https://www.acme.io/en").domain == "acme.io"


def test_extract_json_handles_fences_and_prose():
    assert extract_json('Sure!\n```json\n{"a": {"b": "}"}}\n```') == {"a": {"b": "}"}}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_quote_verification_rejects_paraphrase():
    assert quote_is_verbatim("the reporting is painful and we had to export everything to spreadsheets", REVIEW)
    assert quote_is_verbatim("“The reporting is painful and we had to export everything to spreadsheets”", REVIEW)
    assert not quote_is_verbatim("reporting is weak so we used spreadsheets for everything", REVIEW)


def test_verifier_drops_uncited_claims_and_fake_quotes():
    v = Verifier([Source(id="S1", company="Acme", category="reviews", url="https://x", content=REVIEW)])
    prof = CompanyProfile(
        name="Acme",
        positioning=Claim(text="uncited", sources=[]),
        key_capabilities=[Claim(text="ok", sources=["S1"]), Claim(text="bad id", sources=["S99"])],
        quotes=[
            Quote(quote="Setup took a single afternoon though", sentiment="praise", source="S1"),
            Quote(quote="Best tool ever made, flawless", sentiment="praise", source="S1"),
        ],
    )
    cleaned, stats = v.clean(prof)
    assert cleaned.positioning is None
    assert [c.text for c in cleaned.key_capabilities] == ["ok"]
    assert len(cleaned.quotes) == 1
    assert stats.claims_dropped == 2 and stats.quotes_dropped == 1


def test_bias_rules_vendor_quotes_and_rival_sources():
    srcs = [
        Source(id="S1", company="Rival", category="comparison", url="https://acme.com/vs-rival",
               content="Rival is slow and customers hate it. Our customers love us, it is amazing.",
               origin="vendor:Acme"),
        Source(id="S2", company="Rival", category="reviews", url="https://g2.com/rival",
               content="Rival support is slow according to many reviewers here.", origin="independent"),
    ]
    v = Verifier(srcs)
    # A testimonial hosted on a vendor's own site is dropped even if verbatim
    prof = CompanyProfile(name="Acme", quotes=[
        Quote(quote="Our customers love us, it is amazing", sentiment="praise", source="S1")])
    cleaned, stats = v.clean(prof)
    assert cleaned.quotes == [] and stats.vendor_quotes_dropped == 1
    # A claim ABOUT Rival can't rest only on Acme's own blog...
    claims = [Claim(text="Rival is slow", sources=["S1"]), Claim(text="Rival support is slow", sources=["S1", "S2"])]
    kept, stats = v.clean(CompanyProfile(name="Rival", review_weaknesses=claims), about="Rival")
    assert [c.text for c in kept.review_weaknesses] == ["Rival support is slow"]
    assert kept.review_weaknesses[0].sources == ["S2"] and stats.rival_only_dropped == 1


def test_classify_origin_and_numbers():
    from intel.domain.origins import classify_origin
    from intel.domain.ratings import number_in_text

    cos = [Company("Acme", "acme.com"), Company("Rival", "rival.io")]
    assert classify_origin("https://blog.acme.com/x", "Rival", cos) == "vendor:Acme"
    assert classify_origin("https://www.prnewswire.com/news/rival", "Rival", cos) == "vendor:Rival"
    assert classify_origin("https://g2.com/products/rival", "Rival", cos) == "independent"
    assert number_in_text(4.5, "rated 4.5 out of 5") and not number_in_text(4.5, "rated 4.55")
    assert number_in_text(1320, "1,320 reviews") and not number_in_text(132, "1,320 reviews")


# ── evidence layers ─────────────────────────────────────────
def _src(i, url, content=REVIEW, origin="independent", category="reviews"):
    return Source(id=i, company="Rival", category=category, url=url, content=content, origin=origin)


def test_excerpts_must_be_verbatim_and_set_support():
    from intel.models import Excerpt, Point

    v = Verifier([_src("S1", "https://g2.com/a"), _src("S2", "https://reddit.com/r/x"),
                  _src("S3", "https://acme.com/blog", origin="vendor:Acme")])
    ok = Excerpt(source="S1", text="Setup took a single afternoon though")
    point = Point(headline="Fast setup", sources=[], evidence=[
        ok, Excerpt(source="S2", text="Setup took a single afternoon though"),
        Excerpt(source="S1", text="Setup is effortless and instant"),  # paraphrase
    ])
    cleaned, stats = v.clean(point)
    assert cleaned.support == "corroborated" and cleaned.sources == ["S1", "S2"]
    assert stats.excerpts_dropped == 1

    single, _ = v.clean(Point(headline="x", evidence=[ok]))
    assert single.support == "single_source"
    vendor, _ = v.clean(Point(headline="x", evidence=[Excerpt(source="S3", text="Setup took a single afternoon though")]))
    assert vendor.support == "vendor_claim"
    cited, _ = v.clean(Point(headline="x", sources=["S1"], evidence=[Excerpt(source="S1", text="made up words here ok")]))
    assert cited.support == "cited_only"
    # Our own blog is not evidence about the rival: the excerpt goes, and with nothing else the claim goes too
    gone, stats = v.clean(Point(headline="x", evidence=[Excerpt(source="S3", text="Setup took a single afternoon though")]),
                          about="Rival")
    assert gone is None and stats.excerpts_dropped == 1


def test_source_kind():
    from intel.domain.support import source_kind

    assert source_kind(_src("S1", "https://www.g2.com/x")) == "review"
    assert source_kind(_src("S1", "https://reddit.com/r/x")) == "community"
    assert source_kind(_src("S1", "https://acme.com", origin="vendor:Acme")) == "vendor"
    assert source_kind(_src("S1", "https://en.wikipedia.org/wiki/X")) == "reference"
    assert source_kind(_src("S1", "https://techcrunch.com/x", category="news")) == "news"
    assert source_kind({"url": "https://blog.example.com/a-vs-b", "category": "comparison"}) == "analysis"


def test_a_review_of_us_is_not_evidence_about_them():
    from intel.models import Excerpt, Landmine

    v = Verifier([_src("S1", "https://trustradius.com/acme", content=REVIEW) .model_copy(update={"company": "Acme"}),
                  _src("S2", "https://blog.example.com/acme-vs-rival", category="comparison")], ["Acme", "Rival"])
    text = "Setup took a single afternoon though"
    lm = Landmine(question="q", why="w", evidence=[Excerpt(source="S1", text=text)])
    assert v.clean(lm, about="Rival")[0] is None  # Acme's review can't prove a Rival weakness
    lm2 = Landmine(question="q", why="w", evidence=[Excerpt(source="S2", text=text)])
    assert v.clean(lm2, about="Rival")[0].support == "single_source"  # head-to-head pages cover both


def test_proof_quotes_must_help_our_side():
    from intel.analyze import Analyst
    from intel.config import Config
    from intel.models import Quote

    a = Analyst(Config(company=Company("Acme", "acme.com"), competitors=[Company("Rival", "rival.io")]), None,
                [_src("S1", "https://g2.com/acme").model_copy(update={"company": "Acme"}), _src("S2", "https://g2.com/rival")])
    q = lambda s, src: Quote(quote="x" * 20, sentiment=s, source=src)  # noqa: E731
    assert a._backs_us(q("praise", "S1"), "Rival") and a._backs_us(q("pain", "S2"), "Rival")
    assert not a._backs_us(q("pain", "S1"), "Rival")  # our own customer's complaint
    assert not a._backs_us(q("praise", "S2"), "Rival")  # their happy customer
