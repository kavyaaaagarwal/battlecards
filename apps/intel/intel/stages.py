"""The six stages of a research run. Each reads the run document, does one bounded piece of
work (well under the 300s function limit), and records its results in the document."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Callable

from .analyze import Analyst
from .cache import DiskCache
from .collect import collect_sources
from .config import Config
from .domain.views import build_views
from .llm import LLM
from .models import CompanyProfile, Source
from .runs import Budget, run_key
from .search import SearchProvider, make_search_provider
from .store import Store

log = logging.getLogger(__name__)


@dataclass
class Deps:
    make_search: Callable[[Config, DiskCache], SearchProvider] = make_search_provider
    make_llm: Callable[[Config], Any] = LLM


@dataclass
class StageContext:
    cfg: Config
    store: Store
    doc: dict
    deps: Deps
    deadline: float
    _cache: DiskCache | None = field(default=None, repr=False)

    @property
    def cache(self) -> DiskCache:
        if self._cache is None:
            self._cache = DiskCache(self.store, self.cfg.cache_ttl_hours)
        return self._cache

    def save(self) -> None:
        self.store.put_json(run_key(self.doc["id"]), self.doc)

    def sources(self) -> list[Source]:
        return [Source(**s) for s in self.doc["sources"]]

    def profiles(self) -> dict[str, CompanyProfile]:
        return {k: CompanyProfile(**v) for k, v in self.doc["profiles"].items()}

    def llm(self):
        llm = self.deps.make_llm(self.cfg)
        llm.deadline = self.deadline
        return llm

    def absorb(self, llm, analyst: Analyst | None = None) -> None:
        """Add this stage's token usage, models and verification stats to the run totals."""
        for k, v in (getattr(llm, "usage", None) or {}).items():
            self.doc["usage"][k] = self.doc["usage"].get(k, 0) + v
        models = set(self.doc.get("models_used") or []) | set(getattr(llm, "models_used", None) or [])
        if not models and getattr(llm, "model", None):
            models = {llm.model}
        self.doc["models_used"] = sorted(models)
        self.doc["model"] = ", ".join(self.doc["models_used"])
        if analyst:
            for k, v in asdict(analyst.stats).items():
                if k != "dropped_examples":
                    self.doc["stats"][k] = self.doc["stats"].get(k, 0) + v


class StageError(RuntimeError):
    pass


def load_notes(cfg: Config) -> dict[str, str]:
    """Optional human analysis: notes/<competitor-slug>.md and notes/positioning.md."""
    notes = {}
    for comp in cfg.competitors:
        f = cfg.notes_dir / f"{comp.slug}.md"
        if f.exists():
            notes[comp.name] = f.read_text()
    f = cfg.notes_dir / "positioning.md"
    if f.exists():
        notes["_positioning"] = f.read_text()
    return notes


# ── 1. collect ────────────────────────────────────────────────
def collect(ctx: StageContext) -> str:
    cfg, note = ctx.cfg, ""
    budget = Budget(ctx.store, ctx.doc["run_date"])
    if cfg.resolved_search_provider == "tavily" and budget.get()["tavily_calls"] >= cfg.tavily_calls_per_day:
        cfg = replace(cfg, search_provider="ddg")
        ctx.doc["degraded"] = True
        note = "Today's search budget is used up - using DuckDuckGo (fewer review sources). "
    search = ctx.deps.make_search(cfg, ctx.cache)
    stats: dict = {}
    # Leave headroom under the stage budget for saving and the slowest in-flight request
    sources, facts = collect_sources(cfg, search, ctx.cache, deadline=ctx.deadline - 40, stats=stats)
    if stats.get("searches_done", 0) < stats.get("searches_planned", 0):
        note += f"Time limit reached - used {stats['searches_done']} of {stats['searches_planned']} searches. "
    if getattr(search, "refused", False):
        ctx.doc["degraded"] = True
        note += "Tavily's search credits are used up - switched to DuckDuckGo (fewer review sources). "
    if not sources:
        raise StageError("No sources found - check the company names and domains.")
    if search.name == "tavily":
        budget.add(tavily_calls=getattr(search, "api_calls", 0))
    indie = sum(1 for s in sources if s.origin == "independent")
    ctx.doc.update(
        sources=[s.model_dump() for s in sources],
        facts=facts,
        search_provider=search.name,
        domains={c.name: c.domain for c in cfg.all_companies},
    )
    return f"{note}{len(sources)} sources, {indie} independent"


# ── 2. profiles ───────────────────────────────────────────────
def profiles(ctx: StageContext) -> str:
    llm = ctx.llm()
    analyst = Analyst(ctx.cfg, llm, ctx.sources())
    todo = [c for c in ctx.cfg.all_companies if c.name not in ctx.doc["profiles"]]
    errors = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(analyst.profile, c): c for c in todo}
        for f in as_completed(futures):
            c = futures[f]
            try:
                ctx.doc["profiles"][c.name] = f.result().model_dump()
            except Exception as e:  # noqa: BLE001
                errors.append(f"{c.name}: {e}")
            ctx.save()  # every finished company survives a retry
    ctx.absorb(llm, analyst)
    if errors:
        raise StageError("; ".join(errors))
    order = [c.name for c in ctx.cfg.all_companies]
    ctx.doc["profiles"] = {n: ctx.doc["profiles"][n] for n in order}
    return f"{len(order)} companies profiled"


# ── 3. battlecards ────────────────────────────────────────────
def battlecards(ctx: StageContext) -> str:
    llm = ctx.llm()
    analyst = Analyst(ctx.cfg, llm, ctx.sources())
    profs = ctx.profiles()
    done = {b["competitor"] for b in ctx.doc["battlecards"]}
    todo = [c for c in ctx.cfg.competitors if c.name not in done]
    errors = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(analyst.battlecard, profs, c): c for c in todo}
        for f in as_completed(futures):
            c = futures[f]
            try:
                ctx.doc["battlecards"].append(f.result().model_dump())
            except Exception as e:  # noqa: BLE001
                errors.append(f"{c.name}: {e}")
            ctx.save()
    ctx.absorb(llm, analyst)
    if errors:
        raise StageError("; ".join(errors))
    order = {c.name: i for i, c in enumerate(ctx.cfg.competitors)}
    ctx.doc["battlecards"].sort(key=lambda b: order.get(b["competitor"], 99))
    return f"{len(ctx.doc['battlecards'])} battlecards"


# ── 4. matrix (optional) ──────────────────────────────────────
def matrix(ctx: StageContext) -> str:
    llm = ctx.llm()
    analyst = Analyst(ctx.cfg, llm, ctx.sources())
    try:
        result = analyst.matrix(ctx.profiles())
    finally:
        ctx.absorb(llm, analyst)
    ctx.doc["matrix"] = result.model_dump()
    return f"{len(result.capabilities)} capabilities compared"


# ── 5. positioning (optional) ─────────────────────────────────
def positioning(ctx: StageContext) -> str:
    llm = ctx.llm()
    analyst = Analyst(ctx.cfg, llm, ctx.sources())
    try:
        result = analyst.positioning(ctx.profiles())
    finally:
        ctx.absorb(llm, analyst)
    ctx.doc["positioning"] = result.model_dump()
    return ""


# ── 6. finalize ───────────────────────────────────────────────
def find_previous(store: Store, doc: dict) -> dict | None:
    best = None
    for key in store.list_keys("runs/"):
        other = store.get_json(key)
        if (other and other.get("company_key") == doc["company_key"] and other.get("run_date", "") < doc["run_date"]
                and other.get("status") in ("succeeded", "partial")):
            if best is None or other["run_date"] > best["run_date"]:
                best = other
    return best


def finalize(ctx: StageContext) -> str:
    note = ""
    previous = find_previous(ctx.store, ctx.doc)
    if previous:
        ctx.doc["previous_run"] = previous["run_date"]
        llm = ctx.llm()
        analyst = Analyst(ctx.cfg, llm, ctx.sources())
        try:
            ctx.doc["changes"] = analyst.changes(previous, ctx.profiles()).model_dump()
        except Exception as e:  # noqa: BLE001 - the diff is a nice-to-have
            log.warning("Skipped change diff: %s", e)
            note = "Change diff skipped. "
        ctx.absorb(llm, analyst)
    ctx.doc["notes"] = load_notes(ctx.cfg)
    ctx.doc["views"] = build_views(ctx.doc)
    skipped = any(p["status"] == "skipped" for p in ctx.doc["progress"])
    ctx.doc["status"] = "partial" if skipped else "succeeded"
    ctx.doc["current_stage"] = None
    return note + ("Some optional sections were skipped." if skipped else "Report ready")


STAGE_FUNCS: dict[str, Callable[[StageContext], str | None]] = {
    "collect": collect, "profiles": profiles, "battlecards": battlecards,
    "matrix": matrix, "positioning": positioning, "finalize": finalize,
}
