"""Typed schemas. Every factual statement carries `sources` (source IDs like "S12")
so it can be verified and rendered as a clickable citation."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    id: str
    company: str
    category: str
    url: str
    title: str = ""
    content: str = ""
    published: str | None = None
    # Who published it: "independent", or "vendor:<Company>" for a company's own site/press release.
    origin: str = "independent"

    @property
    def vendor(self) -> str | None:
        return self.origin.split(":", 1)[1] if self.origin.startswith("vendor:") else None


class Claim(BaseModel):
    text: str
    sources: list[str] = Field(default_factory=list)


class PriceTier(BaseModel):
    name: str
    price: str = Field(description="As stated, e.g. '$49/agent/month billed annually' or 'Contact sales'")
    notable: str = ""
    sources: list[str] = Field(default_factory=list)


class Quote(BaseModel):
    quote: str = Field(description="Verbatim text copied exactly from the source")
    sentiment: Literal["praise", "pain", "switching"]
    source: str


class Rating(BaseModel):
    site: str = Field(description="Review site, e.g. 'G2', 'Capterra'")
    rating: float = Field(description="Average star rating exactly as shown in the source")
    out_of: float = 5
    review_count: int | None = Field(None, description="Number of reviews, only if stated")
    source: str


class CompanyProfile(BaseModel):
    name: str = ""  # overwritten with the configured name after the call
    domain: str | None = None
    positioning: Claim | None = Field(None, description="How the company describes itself, in one line")
    target_customers: list[Claim] = Field(default_factory=list)
    key_capabilities: list[Claim] = Field(default_factory=list)
    pricing_summary: Claim | None = None
    pricing_tiers: list[PriceTier] = Field(default_factory=list)
    recent_changes: list[Claim] = Field(default_factory=list)
    review_strengths: list[Claim] = Field(default_factory=list)
    review_weaknesses: list[Claim] = Field(default_factory=list)
    hiring_signals: list[Claim] = Field(default_factory=list)
    ratings: list[Rating] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)


class Landmine(BaseModel):
    question: str = Field(description="A question our rep asks that exposes a competitor weakness")
    why: str
    sources: list[str] = Field(default_factory=list)


class Objection(BaseModel):
    objection: str = Field(description="What a prospect says in favour of the competitor")
    response: str
    sources: list[str] = Field(default_factory=list)


class Point(BaseModel):
    headline: str = Field(description="Scannable takeaway, max 10 words")
    detail: str = Field("", description="One supporting sentence, max 25 words")
    sources: list[str] = Field(default_factory=list)


class Threat(Point):
    counter: str = Field("", description="How a rep neutralises this, max 20 words")


class Battlecard(BaseModel):
    competitor: str
    overview: str = Field("", description="One sentence: who they are and who they sell to")
    tldr: str = Field(description="Two short sentences: when we win, when we usually lose")
    quick_dismiss: str = Field(
        "", description="Talk track, max 50 words: acknowledge their strength, name the limit, pivot to our value"
    )
    where_we_win: list[Point] = Field(default_factory=list)
    where_we_lose: list[Threat] = Field(default_factory=list)
    landmines: list[Landmine] = Field(default_factory=list)
    objections: list[Objection] = Field(default_factory=list)
    pricing_comparison: Claim | None = None
    proof_quotes: list[Quote] = Field(default_factory=list)


class SharedClaim(BaseModel):
    theme: str
    companies: list[str]
    sources: list[str] = Field(default_factory=list)


class WhiteSpace(BaseModel):
    opportunity: str
    evidence: str
    sources: list[str] = Field(default_factory=list)


class PositioningAnalysis(BaseModel):
    table_stakes: list[SharedClaim] = Field(
        default_factory=list, description="Themes most players claim - not differentiating"
    )
    white_space: list[WhiteSpace] = Field(
        default_factory=list, description="Buyer needs (from reviews) nobody clearly owns"
    )
    recommended_angle: Claim | None = Field(
        None, description="A positioning angle our company could credibly own"
    )


class Change(BaseModel):
    company: str
    change: str
    why_it_matters: str
    severity: Literal["high", "medium", "low"]
    sources: list[str] = Field(default_factory=list)


class ChangeReport(BaseModel):
    changes: list[Change] = Field(default_factory=list)


class Cell(BaseModel):
    company: str
    status: Literal["full", "partial", "none", "unknown"] = "unknown"
    note: str = Field("", description="Max 8 words, e.g. 'Add-on, extra cost'")
    sources: list[str] = Field(default_factory=list)


class Capability(BaseModel):
    name: str = Field(description="Buyer-facing capability, max 5 words")
    cells: list[Cell] = Field(default_factory=list)


class CapabilityMatrix(BaseModel):
    capabilities: list[Capability] = Field(default_factory=list)
