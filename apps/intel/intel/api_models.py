"""Response models: the public contract that generates the web app's TypeScript types."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import Battlecard, CapabilityMatrix, ChangeReport, CompanyProfile, PositioningAnalysis, Rating

RunStatus = Literal["queued", "running", "succeeded", "partial", "failed"]
StageStatus = Literal["running", "done", "skipped", "retrying", "failed"]
Status = Literal["full", "partial", "none", "unknown"]


class CreateRunOut(BaseModel):
    run_id: str
    status: RunStatus
    reused: bool


class ProgressItem(BaseModel):
    stage: str
    status: StageStatus
    at: str
    note: str = ""


class RunStatusOut(BaseModel):
    id: str
    status: RunStatus
    current_stage: str | None = None
    progress: list[ProgressItem]
    degraded: bool = False
    error: str | None = None
    created_at: str
    company: str
    competitors: list[str]


class RunSummary(BaseModel):
    id: str
    status: RunStatus
    created_at: str
    run_date: str
    company: str
    competitors: list[str]
    category: str = ""
    featured: bool = False


class SourceOut(BaseModel):
    id: str
    company: str
    category: str
    url: str
    title: str = ""
    published: str | None = None
    origin: str = "independent"


class CompanyFacts(BaseModel):
    wikipedia: str | None = None
    founded: str | None = None
    employees: str | None = None
    headquarters: str | None = None
    owner: str | None = None


class CellView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    company: str = ""
    status: Status = "unknown"
    note: str = ""
    sources: list[str] = Field(default_factory=list)
    self_reported: bool = Field(False, alias="self")


class CapabilityView(BaseModel):
    name: str
    cells: list[CellView]


class CapRow(BaseModel):
    name: str
    us: CellView
    them: CellView
    verdict: Literal["lead", "even", "behind", "unknown"]


class Tally(BaseModel):
    lead: int
    even: int
    behind: int
    unknown: int


class RatingPair(BaseModel):
    site: str
    us: Rating | None = None
    them: Rating | None = None


class Evidence(BaseModel):
    total: int
    independent: int
    pct: int


class CardView(BaseModel):
    rows: list[CapRow]
    tally: Tally
    known: int
    ratings: list[RatingPair]
    axis_lo: float
    evidence: Evidence


class MarketRating(BaseModel):
    name: str
    by_site: dict[str, Rating]


class Views(BaseModel):
    cards: list[CardView]
    names: list[str]
    sites: list[str]
    market_ratings: list[MarketRating]
    matrix: list[CapabilityView]


class ReportOut(BaseModel):
    id: str
    status: RunStatus
    run_date: str
    company: str
    competitors: list[str]
    category: str = ""
    model: str = ""
    search_provider: str = ""
    previous_run: str | None = None
    degraded: bool = False
    featured: bool = False
    profiles: dict[str, CompanyProfile]
    battlecards: list[Battlecard]
    matrix: CapabilityMatrix | None = None
    positioning: PositioningAnalysis | None = None
    changes: ChangeReport | None = None
    facts: dict[str, CompanyFacts] = Field(default_factory=dict)
    sources: list[SourceOut]
    stats: dict[str, int] = Field(default_factory=dict)
    usage: dict[str, int] = Field(default_factory=dict)
    notes: dict[str, str] = Field(default_factory=dict)
    views: Views
