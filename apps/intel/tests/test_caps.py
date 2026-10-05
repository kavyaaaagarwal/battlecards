"""A battlecard must fit on one screen: item caps are enforced in code."""
from intel.analyze import Analyst
from intel.config import Company, Config
from intel.models import Battlecard, CompanyProfile, Source


class FiveOfEverything:
    usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def structured(self, system, prompt, schema, max_tokens=8000):
        pt = {"headline": "h", "detail": "d", "sources": ["S1"]}
        return schema(
            competitor="Rival", tldr="t",
            where_we_win=[pt] * 5, where_we_lose=[pt] * 5,
            landmines=[{"question": "q", "why": "w", "sources": ["S1"]}] * 5,
            objections=[{"objection": "o", "response": "r", "sources": ["S1"]}] * 5,
            proof_quotes=[],
        )


def test_battlecard_items_are_capped():
    cfg = Config(company=Company("Acme"), competitors=[Company("Rival")])
    src = Source(id="S1", company="Rival", category="reviews", url="https://g2.com/x", content="c" * 100)
    analyst = Analyst(cfg, FiveOfEverything(), [src])
    profiles = {"Acme": CompanyProfile(name="Acme"), "Rival": CompanyProfile(name="Rival")}
    card: Battlecard = analyst.battlecard(profiles, Company("Rival"))
    assert (len(card.where_we_win), len(card.where_we_lose), len(card.landmines), len(card.objections)) == (3, 3, 3, 3)
