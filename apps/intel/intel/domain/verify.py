"""Guards against hallucination: drop uncited claims and non-verbatim quotes."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from pydantic import BaseModel
from rapidfuzz import fuzz

from ..models import Quote, Source

# Models that represent a single factual statement - dropped if left with no valid source
CITED_TYPES = {"Claim", "Point", "Threat", "PriceTier", "Landmine", "Objection", "SharedClaim", "WhiteSpace", "Change"}


@dataclass
class VerifyStats:
    claims_dropped: int = 0
    quotes_dropped: int = 0
    bad_ids_removed: int = 0
    vendor_quotes_dropped: int = 0
    rival_only_dropped: int = 0
    dropped_examples: list[str] = field(default_factory=list)

    def merge(self, other: "VerifyStats") -> None:
        self.claims_dropped += other.claims_dropped
        self.quotes_dropped += other.quotes_dropped
        self.bad_ids_removed += other.bad_ids_removed
        self.vendor_quotes_dropped += other.vendor_quotes_dropped
        self.rival_only_dropped += other.rival_only_dropped
        self.dropped_examples += other.dropped_examples


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "..."}))
    text = re.sub(r"[*_#>`]", "", text)  # markdown emphasis survives in raw content
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_is_verbatim(quote: str, source_text: str) -> bool:
    q, s = _norm(quote).strip(" \"'."), _norm(source_text)
    if len(q) < 15:
        return False
    if q in s:
        return True
    # tolerate tiny differences (ellipsis, a stray character) - not paraphrase
    return fuzz.partial_ratio(q, s) >= 94


class Verifier:
    def __init__(self, sources: list[Source]):
        self.by_id = {s.id: s for s in sources}

    def clean(self, obj: BaseModel, about: str | None = None) -> tuple[BaseModel, VerifyStats]:
        """`about`: the company these claims describe. A rival vendor's own site is not
        evidence about it (e.g. our blog saying a competitor is slow), so those citations
        are ignored - and a claim left with no other source is dropped."""
        stats = VerifyStats()
        cleaned = self._walk(obj, stats, about)
        return cleaned, stats

    def _usable(self, sid: str, about: str | None) -> bool:
        src = self.by_id.get(sid)
        return bool(src) and not (about and src.vendor and src.vendor != about)

    def _walk(self, obj, stats: VerifyStats, about: str | None = None):
        if isinstance(obj, list):
            out = [self._walk(x, stats, about) for x in obj]
            return [x for x in out if x is not None]
        if not isinstance(obj, BaseModel):
            return obj

        if isinstance(obj, Quote):
            src = self.by_id.get(obj.source)
            if src and src.vendor:  # testimonials hosted by a vendor are curated marketing
                stats.vendor_quotes_dropped += 1
                stats.dropped_examples.append(f"vendor-hosted quote: {obj.quote[:80]}")
                return None
            if src and quote_is_verbatim(obj.quote, src.content):
                return obj
            stats.quotes_dropped += 1
            stats.dropped_examples.append(f"quote: {obj.quote[:80]}")
            return None

        updates = {}
        rival_only = False
        for name in type(obj).model_fields:
            value = getattr(obj, name)
            if name == "sources" and isinstance(value, list):
                known = [sid for sid in dict.fromkeys(value) if sid in self.by_id]
                stats.bad_ids_removed += len(value) - len(known)
                updates[name] = [sid for sid in known if self._usable(sid, about)]
                rival_only = bool(known) and not updates[name]
            elif isinstance(value, (BaseModel, list)):
                updates[name] = self._walk(value, stats, about)

        new = obj.model_copy(update=updates)
        if type(obj).__name__ in CITED_TYPES and not getattr(new, "sources", None):
            if rival_only:
                stats.rival_only_dropped += 1
            else:
                stats.claims_dropped += 1
            text = getattr(obj, "text", None) or getattr(obj, "question", None) or str(obj)[:80]
            stats.dropped_examples.append(f"{'rival-sourced' if rival_only else 'uncited'}: {str(text)[:80]}")
            return None
        return new
