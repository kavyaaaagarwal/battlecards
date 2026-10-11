from intel.domain.categories import build_categories, category_of, classify, point_tags


def test_classify_maps_buyer_language_to_standard_categories():
    assert classify("Pricing transparency") == "pricing"
    assert classify("Have you read the auto-renewal terms?") == "pricing"
    assert classify("Implementation speed and support") == "implementation"  # specific beats generic
    assert classify("Customer support quality") == "support"
    assert classify("SSO and SOC 2 compliance") == "integrations"
    assert classify("Integrated single platform") == "product"  # "integrated" is a product trait
    assert classify("Paylocity is bigger and more established") == "voice"
    assert classify("Our TrustRadius rating beats theirs") == "rating"
    assert classify("isolved scores higher on usability") == "product"
    assert classify("Payroll and tax filing") == "product"


def test_model_category_wins_over_keywords():
    assert category_of({"name": "Payroll and tax filing", "category": "support"}) == "support"
    assert category_of({"name": "Payroll and tax filing", "category": "nonsense"}) == "product"
    assert category_of({"name": "Vendor stability", "category": "reputation"}) == "voice"  # pre-split tag


def cell(company, status):
    return {"company": company, "status": status, "sources": ["S1"]}


RATINGS = {"Acme": {}, "Rival": {}, "Other": {}}


def test_category_scores_leaders_and_edges():
    matrix = [
        {"name": "Reporting", "cells": [cell("Acme", "full"), cell("Rival", "partial"), cell("Other", "unknown")]},
        {"name": "Published pricing", "cells": [cell("Acme", "none"), cell("Rival", "full"), cell("Other", "partial")]},
    ]
    out = build_categories("Acme", ["Acme", "Rival", "Other"], matrix, lambda n: RATINGS[n])
    cats = {c["id"]: c for c in out["categories"]}

    assert cats["product"]["scores"] == {"Acme": 1.0, "Rival": 0.5, "Other": None}
    assert cats["product"]["leader"] == "Acme"
    assert cats["pricing"]["leader"] == "Rival"
    assert cats["support"]["basis"] == "no evidence" and cats["support"]["leader"] is None

    assert out["edges"]["Rival"]["product"] == -0.5   # we're ahead
    assert out["edges"]["Rival"]["pricing"] == 1.0    # they're ahead
    assert out["edges"]["Rival"]["support"] is None   # no evidence is not "even"
    assert out["edges"]["Other"]["product"] is None   # their cell is unknown


def rating(site, stars, count, out_of=5):
    return {"site": site, "rating": stars, "out_of": out_of, "review_count": count}


def test_a_few_glowing_reviews_cannot_outrank_thousands():
    # 4.5 from 31 reviews vs 4.05 from 2,841 on the same site: after the pull to the site
    # average, the small sample is unproven and the two are effectively even.
    r = {"Acme": {"TR": rating("TR", 9.0, 31, 10)},
         "Big": {"TR": rating("TR", 8.1, 2841, 10), "Gartner": rating("Gartner", 4.1, 729)},
         "Mid": {"TR": rating("TR", 7.4, 345, 10), "Gartner": rating("Gartner", 4.1, 93)}}
    out = build_categories("Acme", ["Acme", "Big", "Mid"], [], lambda n: r[n])
    cats = {c["id"]: c for c in out["categories"]}
    assert cats["rating"]["leader"] is None                       # no clear rating leader
    assert abs(out["edges"]["Big"]["rating"]) <= 0.1              # reads as even
    assert cats["rating"]["thin"] == ["Acme"]                     # flagged: under 50 reviews
    assert cats["voice"]["leader"] == "Big" and out["edges"]["Big"]["voice"] > 0.5


def test_ratings_are_only_compared_on_the_same_site():
    # Acme is only on G2, Rival only on Capterra: nothing to compare head to head
    r = {"Acme": {"G2": rating("G2", 4.8, 500)}, "Rival": {"Capterra": rating("Capterra", 3.0, 500)}}
    out = build_categories("Acme", ["Acme", "Rival"], [], lambda n: r[n])
    assert out["edges"]["Rival"]["rating"] is None
    assert out["edges"]["Rival"]["voice"] == 0.0                  # same review volume


def test_no_reviews_means_no_review_categories():
    out = build_categories("Acme", ["Acme", "Rival"], [], lambda n: {})
    cats = {c["id"]: c for c in out["categories"]}
    assert cats["rating"]["basis"] == cats["voice"]["basis"] == "no evidence"
    assert out["edges"]["Rival"]["rating"] is None and out["edges"]["Rival"]["voice"] is None


def test_point_tags_follow_the_headline():
    card = {"where_we_win": [{"headline": "Implementation is free and fast", "analysis": "support praised"}],
            "where_we_lose": [{"headline": "Third-party ecosystem"}],
            "landmines": [{"question": "When is your renewal window?"}],
            "objections": [{"objection": "They have a better mobile app", "response": "Our support..."}]}
    assert point_tags(card) == {"wins": ["implementation"], "losses": ["integrations"],
                                "asks": ["pricing"], "objections": ["product"]}
