"""Run requests, run IDs, and the run document stored at runs/{id}.json."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

from .config import Config, clean_domain
from .store import Store

STAGES = ["collect", "profiles", "battlecards", "matrix", "positioning", "finalize"]
OPTIONAL_STAGES = {"matrix", "positioning"}
RUN_ID_PATTERN = r"^[0-9a-f]{10}$"


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    domain: str | None = Field(None, max_length=100)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Company name is empty")
        return v

    @field_validator("domain")
    @classmethod
    def _domain(cls, v: str | None) -> str | None:
        return clean_domain(v)


class RunRequest(BaseModel):
    company: CompanyIn
    competitors: list[CompanyIn] = Field(min_length=1, max_length=4)
    category: str = Field("", max_length=80)

    @model_validator(mode="after")
    def _check(self) -> "RunRequest":
        names = [c.name.lower() for c in [self.company, *self.competitors]]
        if len(set(names)) != len(names):
            raise ValueError("Company and competitor names must all be different")
        self.category = " ".join(self.category.split())
        return self


def request_from_config(cfg: Config) -> RunRequest:
    return RunRequest(
        company=CompanyIn(name=cfg.company.name, domain=cfg.company.domain),
        competitors=[CompanyIn(name=c.name, domain=c.domain) for c in cfg.competitors],
        category=cfg.category,
    )


def company_key(req: RunRequest) -> str:
    """Identifies 'the same comparison' across days (used to find the previous run)."""
    return req.company.name.lower() + ">" + ",".join(sorted(c.name.lower() for c in req.competitors))


def run_id_for(req: RunRequest, day: str) -> str:
    payload = {
        "key": company_key(req),
        "domains": sorted((c.name.lower(), c.domain or "") for c in [req.company, *req.competitors]),
        "category": req.category.lower(),
        "day": day,
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:10]


def run_key(run_id: str) -> str:
    return f"runs/{run_id}.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_doc(run_id: str, req: RunRequest, day: str) -> dict:
    return {
        "id": run_id, "created_at": now_iso(), "status": "queued", "current_stage": None,
        "featured": False, "degraded": False, "error": None,
        "inputs": req.model_dump(), "company_key": company_key(req),
        "progress": [], "stages_done": [], "domains": {}, "models_used": [],
        # Report fields - same shape as the POC's snapshot.json
        "run_date": day, "company": req.company.name, "competitors": [c.name for c in req.competitors],
        "category": req.category, "model": "", "search_provider": "", "previous_run": None,
        "facts": {}, "sources": [], "profiles": {}, "battlecards": [], "matrix": None,
        "positioning": {}, "changes": None, "views": None, "notes": {},
        "stats": {"claims_dropped": 0, "quotes_dropped": 0, "bad_ids_removed": 0,
                  "vendor_quotes_dropped": 0, "rival_only_dropped": 0},
        "usage": {"calls": 0, "input_tokens": 0, "output_tokens": 0},
    }


def mark(doc: dict, stage: str, status: str, note: str = "") -> None:
    entry = {"stage": stage, "status": status, "at": now_iso(), "note": note}
    doc["progress"] = [p for p in doc["progress"] if p["stage"] != stage] + [entry]


class Budget:
    """Daily counters (runs started, Tavily calls) for the global free-tier caps.
    Read-modify-write without locking: slightly imprecise under bursts, fine for a demo."""

    def __init__(self, store: Store, day: str):
        self.store, self.key = store, f"usage/{day}.json"

    def get(self) -> dict:
        return {"runs": 0, "tavily_calls": 0, **(self.store.get_json(self.key) or {})}

    def add(self, **increments: int) -> None:
        d = self.get()
        for k, v in increments.items():
            d[k] = d.get(k, 0) + v
        self.store.put_json(self.key, d)


class CapacityError(RuntimeError):
    pass


def create_run(store: Store, req: RunRequest, *, day: str | None = None, featured: bool = False,
               runs_per_day: int | None = None) -> tuple[dict, bool]:
    """Returns (run document, reused). Same request on the same day reuses the run unless it failed."""
    day = day or date.today().isoformat()
    run_id = run_id_for(req, day)
    existing = store.get_json(run_key(run_id))
    if existing and existing.get("status") != "failed":
        return existing, True
    budget = Budget(store, day)
    if runs_per_day is not None and budget.get()["runs"] >= runs_per_day:
        raise CapacityError(
            f"Today's limit of {runs_per_day} new research runs is used up. "
            "Try again tomorrow, or explore the featured reports."
        )
    doc = new_run_doc(run_id, req, day)
    doc["featured"] = featured
    store.put_json(run_key(run_id), doc)
    budget.add(runs=1)
    return doc, False
