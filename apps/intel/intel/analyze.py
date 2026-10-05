"""LLM analysis stages: profiles -> battlecards -> positioning -> change diff."""
from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from . import prompts
from .config import Company, Config
from .domain.origins import origin_label
from .domain.ratings import number_in_text, verify_ratings  # noqa: F401  (number_in_text re-exported for tests)
from .domain.verify import Verifier, VerifyStats
from .llm import LLM
from .models import (
    Battlecard,
    CapabilityMatrix,
    Cell,
    ChangeReport,
    CompanyProfile,
    PositioningAnalysis,
    Source,
)
from .search import domain_of

log = logging.getLogger(__name__)


def format_sources(sources: list[Source]) -> str:
    blocks = []
    for s in sources:
        date = f" | published {s.published}" if s.published else ""
        blocks.append(
            f"[{s.id}] ({s.category} | {origin_label(s)} | {domain_of(s.url)}{date}) {s.title}\nURL: {s.url}\n{s.content}"
        )
    return "\n\n---\n\n".join(blocks) or "(no sources found)"


def _strip_ids(obj):
    if isinstance(obj, dict):
        return {k: _strip_ids(v) for k, v in obj.items() if k not in ("sources", "source")}
    if isinstance(obj, list):
        return [_strip_ids(x) for x in obj]
    return obj


def compact(model) -> str:
    return json.dumps(model.model_dump(exclude_none=True), ensure_ascii=False, separators=(",", ":"))


class Analyst:
    def __init__(self, cfg: Config, llm: LLM, sources: list[Source]):
        self.cfg = cfg
        self.llm = llm
        self.sources = sources
        self.verifier = Verifier(sources)
        self.stats = VerifyStats()

    def _verified(self, obj, about: str | None = None):
        cleaned, stats = self.verifier.clean(obj, about)
        self.stats.merge(stats)
        return cleaned

    def _origins(self, *texts: str) -> str:
        """Origin key for every source ID mentioned in the given text blocks."""
        ids = dict.fromkeys(re.findall(r"\bS\d+\b", " ".join(texts)))
        by_id = self.verifier.by_id
        return "\n".join(f"{i}: {origin_label(by_id[i])} ({domain_of(by_id[i].url)})" for i in ids if i in by_id)

    def _verify_ratings(self, prof: CompanyProfile) -> None:
        """Ratings are numbers - keep only ones printed on an independent review-site page."""
        prof.ratings = verify_ratings(prof.ratings, self.verifier.by_id)

    # ── stage 1 ───────────────────────────────────────────────
    def profile(self, c: Company) -> CompanyProfile:
        own = [s for s in self.sources if s.company == c.name and s.category != "comparison"]
        log.info("Profiling %s from %d sources", c.name, len(own))
        prof = self.llm.structured(
            prompts.ANALYST_SYSTEM,
            prompts.profile_prompt(c.name, c.domain, self.cfg.category, format_sources(own)),
            CompanyProfile,
        )
        prof.name, prof.domain = c.name, c.domain
        prof = self._verified(prof, about=c.name)
        self._verify_ratings(prof)
        return prof

    def profiles(self) -> dict[str, CompanyProfile]:
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = pool.map(self.profile, self.cfg.all_companies)
            return {c.name: p for c, p in zip(self.cfg.all_companies, results, strict=True)}

    # ── stage 2 ───────────────────────────────────────────────
    def battlecard(self, profiles: dict[str, CompanyProfile], competitor: Company) -> Battlecard:
        log.info("Writing battlecard vs %s", competitor.name)
        comparison = [s for s in self.sources if s.category == "comparison" and s.company == competitor.name]
        ours, theirs = compact(profiles[self.cfg.company.name]), compact(profiles[competitor.name])
        card = self.llm.structured(
            prompts.ANALYST_SYSTEM,
            prompts.battlecard_prompt(
                self.cfg.company.name, competitor.name, ours, theirs, format_sources(comparison),
                origins=self._origins(ours, theirs),
            ),
            Battlecard,
        )
        card.competitor = competitor.name
        card = self._verified(card)
        # Their strengths and weaknesses are claims ABOUT them: our own pages don't count as proof.
        card.where_we_lose = self._verified(card.where_we_lose, about=competitor.name)
        card.landmines = self._verified(card.landmines, about=competitor.name)
        # A battlecard must fit on one screen; models don't always respect the counts asked for.
        card.where_we_win, card.where_we_lose = card.where_we_win[:3], card.where_we_lose[:3]
        card.landmines, card.objections = card.landmines[:3], card.objections[:3]
        card.proof_quotes = card.proof_quotes[:2]
        return card

    def battlecards(self, profiles) -> list[Battlecard]:
        with ThreadPoolExecutor(max_workers=3) as pool:
            return list(pool.map(lambda c: self.battlecard(profiles, c), self.cfg.competitors))

    def matrix(self, profiles: dict[str, CompanyProfile]) -> CapabilityMatrix:
        log.info("Building capability matrix")
        names = [c.name for c in self.cfg.all_companies]
        block = "\n\n".join(f"## {n}\n{compact(p)}" for n, p in profiles.items())
        indie = [s for s in self.sources if s.category in ("comparison", "market", "alternatives") and not s.vendor]
        result = self.llm.structured(
            prompts.ANALYST_SYSTEM,
            prompts.matrix_prompt(self.cfg.company.name, names, self.cfg.category, block,
                                  format_sources(indie), self._origins(block)),
            CapabilityMatrix,
        )
        rows = []
        for cap in result.capabilities[:8]:
            by_company = {c.company.strip().lower(): c for c in cap.cells}
            cells = []
            for n in names:
                cell = by_company.get(n.lower()) or Cell(company=n)
                cell = self._verified(cell, about=n)
                cell.company = n
                if not cell.sources:  # no usable evidence -> honest "unknown"
                    cell.status, cell.note = "unknown", ""
                cells.append(cell)
            cap.cells = cells
            if any(c.status != "unknown" for c in cells):
                rows.append(cap)
        result.capabilities = rows
        return result

    # ── stage 3 ───────────────────────────────────────────────
    def positioning(self, profiles: dict[str, CompanyProfile]) -> PositioningAnalysis:
        log.info("Analysing positioning landscape")
        block = "\n\n".join(f"## {name}\n{compact(p)}" for name, p in profiles.items())
        result = self.llm.structured(
            prompts.ANALYST_SYSTEM, prompts.positioning_prompt(self.cfg.company.name, block), PositioningAnalysis
        )
        return self._verified(result)

    # ── stage 4 ───────────────────────────────────────────────
    def changes(self, previous: dict, profiles: dict[str, CompanyProfile]) -> ChangeReport:
        log.info("Diffing against previous run (%s)", previous.get("run_date"))
        # Old source IDs mean nothing in this run - strip them so the model can't cite them
        prev_block = json.dumps(_strip_ids(previous.get("profiles", {})), ensure_ascii=False, separators=(",", ":"))
        cur_block = "\n\n".join(f"## {n}\n{compact(p)}" for n, p in profiles.items())
        report = self.llm.structured(
            prompts.ANALYST_SYSTEM,
            prompts.diff_prompt(self.cfg.company.name, prev_block, cur_block),
            ChangeReport,
        )
        return self._verified(report)
