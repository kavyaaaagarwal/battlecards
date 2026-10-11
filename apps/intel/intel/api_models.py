"""Response models: the public contract that generates the web app's TypeScript types."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import Battlecard, CapabilityMatrix, ChangeReport, CompanyProfile, PositioningAnalysis, Rating

RunStatus = Literal["queued", "running", "succeeded", "partial", "failed"]
StageStatus = Literal["running", "done", "skipped", "retrying", "failed"]
Status = Literal["full", "partial", "none", "unknown"]


class ReportRequestIn(BaseModel):
    """A visitor registering interest in beta access. Saved for review; nothing runs."""
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    company: str = Field(min_length=1, max_length=80)
    competitors: str = Field("", max_length=300)
    role: str = Field("", max_length=80)
    note: str = Field("", max_length=1000)


class ReportRequestOut(BaseModel):
    ok: bool = True


class FeaturesOut(BaseModel):
    runs_enabled: bool  # ALLOW_RUNS: on for local and preview (staging), off in production


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


class SourceOut(BaseModel):
    id: str
    company: str
    category: str
    url: str
    title: str = ""
    published: str | None = None
    origin: str = "independent"
    kind: Literal["review", "community", "news", "reference", "analysis", "vendor"] = "analysis"


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
    category: str = "product"
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
    top_site: str | None = None  # the site most insights cite
    top_site_items: int = 0
    items: int = 0


CategoryId = Literal["product", "pricing", "support", "implementation", "integrations", "rating", "voice"]


class PointTags(BaseModel):
    """Category of each talk-track point, index-aligned with the battlecard's lists."""
    wins: list[CategoryId] = Field(default_factory=list)
    losses: list[CategoryId] = Field(default_factory=list)
    asks: list[CategoryId] = Field(default_factory=list)
    objections: list[CategoryId] = Field(default_factory=list)


class CategoryView(BaseModel):
    id: CategoryId
    label: str
    basis: str  # what the score rests on, e.g. "3 capabilities" or "2 review sites"
    leader: str | None = None
    scores: dict[str, float | None]  # 0..1 per company; None = no evidence
    detail: dict[str, str]
    values: dict[str, float | None] = Field(default_factory=dict)  # rating: fair stars; voice: review count
    thin: list[str] = Field(default_factory=list)  # companies whose rating rests on too few reviews


class CardView(BaseModel):
    rows: list[CapRow]
    tally: Tally
    known: int
    ratings: list[RatingPair]
    axis_lo: float
    evidence: Evidence
    tags: PointTags = Field(default_factory=PointTags)
    edges: dict[str, float | None] = Field(default_factory=dict)  # category -> them minus us, -1..1


class MarketRating(BaseModel):
    name: str
    by_site: dict[str, Rating]


class Views(BaseModel):
    cards: list[CardView]
    names: list[str]
    sites: list[str]
    market_ratings: list[MarketRating]
    matrix: list[CapabilityView]
    categories: list[CategoryView] = Field(default_factory=list)


class RatingPoint(BaseModel):
    rating: float
    out_of: float = 5
    rating5: float
    review_count: int | None = None


class Scorecard(BaseModel):
    lead: int
    even: int
    behind: int
    known: int


class CompanyMetrics(BaseModel):
    ratings: dict[str, RatingPoint] = Field(default_factory=dict)
    tiers: dict[str, str] = Field(default_factory=dict)
    scorecard: Scorecard | None = None
    sources: int = 0
    independent: int = 0


class HistoryPoint(BaseModel):
    run_id: str
    run_date: str
    companies: dict[str, CompanyMetrics]


class Signal(BaseModel):
    company: str
    kind: Literal["rating", "reviews", "pricing"]
    text: str
    since: str
    good_for_us: bool | None = None


class History(BaseModel):
    points: list[HistoryPoint] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)


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
    profiles: dict[str, CompanyProfile]
    battlecards: list[Battlecard]
    matrix: CapabilityMatrix | None = None
    positioning: PositioningAnalysis | None = None
    changes: ChangeReport | None = None
    facts: dict[str, CompanyFacts] = Field(default_factory=dict)
    sources: list[SourceOut]
    stats: dict[str, int] = Field(default_factory=dict)
    usage: dict[str, float] = Field(default_factory=dict)  # token counts, plus cost_usd
    notes: dict[str, str] = Field(default_factory=dict)
    views: Views
    history: History = Field(default_factory=History)
