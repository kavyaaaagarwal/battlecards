# Battlecard App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the competitive-intel POC into a portfolio web app: a Next.js (App Router, TypeScript) frontend over a private Python FastAPI "intel" service that runs research as resumable stages and stores runs as JSON files.

**Architecture:** One Vercel project with two Services — `web` (Next.js, public) and `intel` (FastAPI, private via a service binding). A research run is six stages chained through a queue (Vercel Queues in production, an in-process thread locally); each stage reads and updates `runs/{id}.json` in a `Store` (local disk locally, Vercel Blob in production). All evidence/verification/scoring rules stay in the Python `intel.domain` package; the web app only renders.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, uv, pytest, ruff · Next.js (latest stable, App Router), TypeScript, Tailwind, zod, openapi-typescript + openapi-fetch, Vitest + Testing Library, Playwright · Vercel Services, Vercel Queues (`vercel` Python SDK), Vercel Blob.

**Spec:** `docs/superpowers/specs/2026-10-05-battlecard-app-design.md`

## Global Constraints

- Python `>=3.12`; run Python via `uv` from `apps/intel` (`uv run …`).
- Next.js: latest stable from `create-next-app@latest`, App Router, `src/` dir, TypeScript, Node.js 24 LTS.
- Each stage must finish well under Vercel Hobby's **300s** function limit: stage time budget **240s**.
- **$0**: free tiers only. No SQL database, no Redis, no user accounts.
- Storage keys: `runs/{run_id}.json`, `cache/{namespace}/{sha1}.json`, `usage/{YYYY-MM-DD}.json`.
- Run IDs are exactly 10 lowercase hex chars (`^[0-9a-f]{10}$`); every API path parameter is validated against this.
- `intel` is never publicly routed; only `web` calls it (`INTEL_URL`).
- Store methods are synchronous and must never be called from inside a running event loop (FastAPI endpoints are plain `def`; async queue handlers use `asyncio.to_thread`).
- Palette (from the validated dataviz slots): us = `#2a78d6` light / `#3987e5` dark; them = `#eb6834` light / `#d95926` dark.
- Defaults: `RUNS_PER_DAY=30`, `TAVILY_CALLS_PER_DAY=30`, `RUN_MODE=inline` (local) / `queue` (Vercel).
- Every commit message ends with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  ```

## Review Focus

1. **Bad run input** (company listed as its own competitor, duplicate competitor names, blank names, 5+ competitors) must return a clear 400, never start a run. → tests in Task 6 (Python) and Task 15 (zod).
2. **A run that keeps failing** (free model returns garbage, OpenRouter daily limit) must end as `failed` with a readable reason shown in the UI, never an endless spinner. → Task 7 (`test_required_stage_fails_after_max_attempts`), Task 16 (`RunProgress` failed state).
3. **Reports with missing optional data** (no matrix, no ratings, empty positioning, seeded old snapshots) must render empty states, not crash. → Task 3 (`test_views_without_matrix_or_ratings`), Task 13 (`renders a battlecard with empty sections`).
4. **Unknown or malformed run IDs** (including path-traversal like `../x`) must give 404/422, never read outside the store. → Task 5 (`test_local_store_rejects_escaping_keys`), Task 9 (`test_unknown_and_malformed_run_ids`).
5. **The same request submitted twice** (double-click, two visitors) must reuse one run and spend credits once. → Task 6 (`test_create_run_reuses_same_day_request`), Task 9 (`test_create_run_reused_flag`).

---

## Milestone M0 — Safety net

### Task 1: Move the POC into `apps/intel` with a uv project

**Files:**
- Move: `intel/` → `apps/intel/intel/`, `tests/` → `apps/intel/tests/`, `run.py` → `apps/intel/run.py`, `requirements.txt` → `apps/intel/requirements.txt`
- Create: `apps/intel/pyproject.toml`
- Modify: `apps/intel/run.py` (default `--env` path), `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: `apps/intel` as the Python project root; `cd apps/intel && uv run pytest -q` is the test command for all later Python tasks.

- [ ] **Step 1: Move files with git, and move untracked data alongside**

```bash
cd /Users/ritik/Projects/competitive-intel-agent/competitive-intel-agent
mkdir -p apps/intel
git mv intel apps/intel/intel
git mv tests apps/intel/tests
git mv run.py apps/intel/run.py
git mv requirements.txt apps/intel/requirements.txt
mv reports apps/intel/reports 2>/dev/null || true
mv .cache apps/intel/.cache 2>/dev/null || true
mv logs apps/intel/logs 2>/dev/null || true
rm -rf .venv .pytest_cache
```

- [ ] **Step 2: Create `apps/intel/pyproject.toml`**

```toml
[project]
name = "intel"
version = "0.2.0"
description = "Competitive-intelligence research and verification service"
requires-python = ">=3.12"
dependencies = [
    "anthropic>=0.40",
    "openai>=1.50",
    "ddgs>=9.0",
    "trafilatura>=1.12",
    "jinja2>=3.1",
    "markdown>=3.5",
    "pydantic>=2.6",
    "python-dotenv>=1.0",
    "rapidfuzz>=3.0",
    "requests>=2.31",
]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B"]
ignore = ["E501"]
```

- [ ] **Step 3: Make the CLI find the repo-root `.env`**

In `apps/intel/run.py`, change the `--env` argument default:

```python
    ap.add_argument("--env", default=str(ROOT.parents[1] / ".env"), help="config file (default: repo-root .env)")
```

- [ ] **Step 4: Ignore new local folders**

Append to `.gitignore`:

```
data/
apps/intel/.venv/
```

- [ ] **Step 5: Install and run the existing tests**

Run: `cd apps/intel && uv sync && uv run pytest -q`
Expected: `8 passed`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: move POC into apps/intel as a uv project

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Characterization tests (golden views + Markdown) and robustness tests

**Files:**
- Create: `apps/intel/tests/fixtures/netchex_snapshot.json` (copy), `apps/intel/tests/fixtures/netchex_views.json`, `apps/intel/tests/fixtures/netchex_report.md`
- Create: `apps/intel/tests/test_golden.py`, `apps/intel/tests/test_llm.py`, `apps/intel/tests/test_caps.py`

**Interfaces:**
- Consumes: `intel.render.build_views(r: dict) -> dict`, `intel.render.render_markdown(r: dict) -> str`, `intel.llm.LLM`, `intel.analyze.Analyst`.
- Produces: golden fixtures that every later refactor must keep byte-identical. Later tasks change only the import path in `test_golden.py`.

- [ ] **Step 1: Copy the real snapshot and generate golden files from the current code**

```bash
cd apps/intel
mkdir -p tests/fixtures
cp reports/netchex/2026-10-02/snapshot.json tests/fixtures/netchex_snapshot.json
uv run python - <<'EOF'
import json
from pathlib import Path
from intel.render import build_views, render_markdown
fx = Path("tests/fixtures")
snap = json.loads((fx / "netchex_snapshot.json").read_text())
(fx / "netchex_views.json").write_text(json.dumps(build_views(snap), indent=2, ensure_ascii=False, sort_keys=True))
(fx / "netchex_report.md").write_text(render_markdown(snap))
EOF
```

- [ ] **Step 2: Write `tests/test_golden.py`**

```python
"""Characterization tests: the refactor must not change what reps see."""
import json
from pathlib import Path

from intel.render import build_views, render_markdown

FX = Path(__file__).parent / "fixtures"


def snapshot() -> dict:
    return json.loads((FX / "netchex_snapshot.json").read_text())


def test_views_match_golden():
    got = json.loads(json.dumps(build_views(snapshot()), sort_keys=True))
    assert got == json.loads((FX / "netchex_views.json").read_text())


def test_markdown_matches_golden():
    assert render_markdown(snapshot()) == (FX / "netchex_report.md").read_text()
```

- [ ] **Step 3: Write `tests/test_llm.py` (protected behaviour 9)**

```python
"""LLM robustness: empty replies rejected, retries rotate models, provider hiccups retried."""
import threading
import time
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from intel.llm import LLM, LLMError, TransientLLMError


class Thing(BaseModel):
    name: str


def bare_llm(provider="openrouter") -> LLM:
    llm = LLM.__new__(LLM)
    llm.provider, llm.model, llm._fallbacks = provider, "m1", ["m2", "m3"]
    llm.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
    llm._lock, llm.models_used, llm._json_mode = threading.Lock(), set(), True
    llm.deadline = None
    return llm


def test_empty_object_reply_is_rejected_and_retried():
    llm, seen = bare_llm(), []
    replies = ['{"": ""}', '{"name": "Acme"}']

    def fake_complete(system, messages, max_tokens, attempt=0):
        seen.append(attempt)
        return replies[attempt]

    llm._complete = fake_complete
    assert llm.structured("sys", "prompt", Thing).name == "Acme"
    assert seen == [0, 1]


def test_transient_provider_error_is_retried():
    llm, calls = bare_llm(), []

    def fake_complete(system, messages, max_tokens, attempt=0):
        calls.append(attempt)
        if attempt == 0:
            raise TransientLLMError("504 upstream idle timeout")
        return '{"name": "ok"}'

    llm._complete = fake_complete
    assert llm.structured("sys", "prompt", Thing).name == "ok"
    assert calls == [0, 1]


def test_retry_leads_with_next_model_and_disables_reasoning():
    llm, sent = bare_llm(), []

    def create(**kwargs):
        sent.append(kwargs)
        msg = SimpleNamespace(content='{"name": "x"}')
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")],
                               usage=None, model=kwargs["model"], error=None)

    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    llm._complete("sys", [{"role": "user", "content": "hi"}], 100, attempt=1)
    assert sent[0]["model"] == "m2"
    assert sent[0]["extra_body"]["models"] == ["m2", "m3", "m1"]
    assert sent[0]["extra_body"]["reasoning"] == {"effort": "none"}


def test_all_attempts_failing_raises_llm_error():
    llm = bare_llm()
    llm._complete = lambda system, messages, max_tokens, attempt=0: "not json"
    with pytest.raises(LLMError):
        llm.structured("sys", "prompt", Thing)
```

- [ ] **Step 4: Write `tests/test_caps.py` (protected behaviour 8)**

```python
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
```

- [ ] **Step 5: Run the new tests**

Run: `cd apps/intel && uv run pytest -q tests/test_golden.py tests/test_caps.py tests/test_llm.py`
Expected: `test_golden` and `test_caps` PASS. In `test_llm.py`, `bare_llm` sets `llm.deadline`, which the current code ignores, so all four PASS too. (They are characterization tests: they pin current behaviour before refactoring.)

- [ ] **Step 6: Commit**

```bash
git add apps/intel/tests
git commit -m "test: golden views/markdown and LLM robustness characterization tests

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Milestone M1 — Python refactor

### Task 3: Extract `intel.domain` (verify, origins, ratings, views)

**Files:**
- Create: `apps/intel/intel/domain/__init__.py`, `domain/verify.py` (moved), `domain/origins.py`, `domain/ratings.py`, `domain/views.py`
- Modify: `apps/intel/intel/analyze.py`, `apps/intel/intel/collect.py`, `apps/intel/intel/render.py`, `apps/intel/tests/test_pipeline.py`, `apps/intel/tests/test_golden.py`
- Test: `apps/intel/tests/test_views.py`

**Interfaces:**
- Produces:
  - `intel.domain.verify`: `Verifier`, `VerifyStats`, `quote_is_verbatim` (unchanged API).
  - `intel.domain.origins`: `NEWSWIRES: list[str]`, `classify_origin(url: str, query_company: str, companies: list[Company]) -> str`, `origin_label(s: Source) -> str`.
  - `intel.domain.ratings`: `REVIEW_DOMAINS: tuple[str, ...]`, `number_in_text(value, text) -> bool`, `verify_ratings(ratings: list[Rating], by_id: dict[str, Source]) -> list[Rating]`.
  - `intel.domain.views`: `SCORE`, `STATUS_LABEL`, `build_views(r: dict) -> dict` (verbatim move).

- [ ] **Step 1: Write `tests/test_views.py` (protected behaviour 5, 7 + Review Focus 3)**

```python
from intel.domain.views import build_views


def doc(**over):
    base = {
        "company": "Acme", "competitors": ["Rival"],
        "sources": [
            {"id": "S1", "origin": "independent"},
            {"id": "S2", "origin": "vendor:Acme"},
        ],
        "profiles": {}, "matrix": None,
        "battlecards": [{
            "competitor": "Rival",
            "where_we_win": [{"headline": "x", "sources": ["S1", "S2"]}],
            "where_we_lose": [], "landmines": [], "objections": [], "proof_quotes": [],
        }],
    }
    base.update(over)
    return base


def test_evidence_pct_counts_unique_independent_sources():
    ev = build_views(doc())["cards"][0]["evidence"]
    assert ev == {"total": 2, "independent": 1, "pct": 50}


def test_scorecard_excludes_unknown_and_flags_self_reported():
    matrix = {"capabilities": [
        {"name": "A", "cells": [{"company": "Acme", "status": "full", "sources": ["S2"]},
                                {"company": "Rival", "status": "partial", "sources": ["S1"]}]},
        {"name": "B", "cells": [{"company": "Acme", "status": "full", "sources": ["S1"]},
                                {"company": "Rival", "status": "unknown", "sources": []}]},
        {"name": "C", "cells": [{"company": "Acme", "status": "none", "sources": ["S1"]},
                                {"company": "Rival", "status": "full", "sources": ["S1"]}]},
    ]}
    card = build_views(doc(matrix=matrix))["cards"][0]
    assert card["tally"] == {"lead": 1, "even": 0, "behind": 1, "unknown": 1}
    assert card["known"] == 2
    assert card["rows"][0]["us"]["self"] is True   # only Acme's own site
    assert card["rows"][1]["us"]["self"] is False  # independent source


def test_views_without_matrix_or_ratings():
    v = build_views(doc(battlecards=[{"competitor": "Rival"}]))
    assert v["cards"][0]["rows"] == [] and v["cards"][0]["ratings"] == []
    assert v["cards"][0]["evidence"]["pct"] == 0 and v["matrix"] == [] and v["sites"] == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/intel && uv run pytest -q tests/test_views.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'intel.domain'`

- [ ] **Step 3: Create the domain package**

```bash
cd apps/intel
mkdir -p intel/domain
printf '"""Pure product rules: evidence, verification and scoring. No I/O."""\n' > intel/domain/__init__.py
git mv intel/verify.py intel/domain/verify.py
sed -i '' 's/^from .models import Quote, Source$/from ..models import Quote, Source/' intel/domain/verify.py
```

Create `intel/domain/origins.py` (moved from `collect.py` and `analyze.py`):

```python
"""Who published a source: a company (vendor) or someone independent."""
from __future__ import annotations

from ..config import Company
from ..models import Source

# Press-release wires carry the company's own words, so they count as vendor sources.
NEWSWIRES = ["prnewswire.com", "globenewswire.com", "businesswire.com", "accessnewswire.com", "einpresswire.com"]
MARKET = "_market"


def _domain(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc.lower().removeprefix("www.")


def classify_origin(url: str, query_company: str, companies: list[Company]) -> str:
    d = _domain(url)
    for c in companies:
        if c.domain and (d == c.domain or d.endswith("." + c.domain)):
            return f"vendor:{c.name}"
    if any(d.endswith(w) for w in NEWSWIRES) and query_company != MARKET:
        return f"vendor:{query_company}"
    return "independent"


def origin_label(s: Source) -> str:
    return f"BY {s.vendor}" if s.vendor else "INDEPENDENT"
```

Create `intel/domain/ratings.py`:

```python
"""Review-site ratings are numbers: keep only ones printed on an independent review page."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..models import Rating, Source

REVIEW_DOMAINS = ("g2.com", "capterra.com", "trustradius.com", "gartner.com", "getapp.com",
                  "softwareadvice.com", "trustpilot.com", "peerspot.com")


def number_in_text(value: float | int, text: str) -> bool:
    """True if the number appears in the text as written (4.5, 4.50, 1,320, 1320)."""
    if isinstance(value, float) and not value.is_integer():
        pats = [re.escape(f"{value:g}"), re.escape(f"{value:.2f}")]
    else:
        n = int(value)
        pats = [re.escape(f"{n:,}"), re.escape(str(n))]
    return any(re.search(rf"(?<![\d.,]){p}(?![\d])", text) for p in pats)


def verify_ratings(ratings: list[Rating], by_id: dict[str, Source]) -> list[Rating]:
    kept: list[Rating] = []
    for r in ratings:
        src = by_id.get(r.source)
        if not src or src.vendor or not urlparse(src.url).netloc.lower().removeprefix("www.").endswith(REVIEW_DOMAINS):
            continue
        if not (0 < r.rating <= r.out_of) or not number_in_text(r.rating, src.content):
            continue
        if r.review_count is not None and not number_in_text(r.review_count, src.content):
            r.review_count = None
        if all(k.site.lower() != r.site.lower() for k in kept):
            kept.append(r)
    return kept
```

Create `intel/domain/views.py` by **moving verbatim** from `intel/render.py` the block from `SCORE = …` through the end of `build_views` (including `STATUS_LABEL`, `_origin`, `_card_ids`). The file starts with:

```python
"""Chart data for a report: scorecards, rating comparisons, evidence share.

The single implementation of the scoring rules; the web app only draws these numbers."""
from __future__ import annotations
```

followed by the moved code exactly as it is today:

```python
SCORE = {"full": 2, "partial": 1, "none": 0}
STATUS_LABEL = {"full": "Full", "partial": "Partial", "none": "Not offered", "unknown": "Unknown"}


def _origin(src: dict) -> str | None:
    """Vendor name for a vendor-published source, None for independent ones."""
    o = src.get("origin") or "independent"
    return o.split(":", 1)[1] if o.startswith("vendor:") else None


def _card_ids(card: dict) -> list[str]:
    ids = []
    for key in ("where_we_win", "where_we_lose", "landmines", "objections"):
        for x in card.get(key) or []:
            ids += x.get("sources") or []
    if card.get("pricing_comparison"):
        ids += card["pricing_comparison"].get("sources") or []
    ids += [q["source"] for q in card.get("proof_quotes") or []]
    return list(dict.fromkeys(ids))


def build_views(r: dict) -> dict:
    """Pre-computes everything the charts need, so the template only lays things out."""
    by_id = {s["id"]: s for s in r["sources"]}
    us = r["company"]
    profiles = r.get("profiles", {})
    matrix = (r.get("matrix") or {}).get("capabilities") or []
    # A cell backed only by the company's own site is its claim, not independent evidence.
    matrix = [{**cap, "cells": [{**c, "self": bool(c.get("sources")) and all(
        _origin(by_id[i]) == c["company"] for i in c["sources"] if i in by_id)} for c in cap["cells"]]}
        for cap in matrix]

    def ratings_of(name):
        return {x["site"]: x for x in (profiles.get(name) or {}).get("ratings") or []}

    cards = []
    for card in r["battlecards"]:
        them = card["competitor"]
        # Head-to-head capability rows
        rows, tally = [], {"lead": 0, "even": 0, "behind": 0, "unknown": 0}
        for cap in matrix:
            cells = {c["company"]: c for c in cap["cells"]}
            a, b = cells.get(us, {"status": "unknown"}), cells.get(them, {"status": "unknown"})
            if a["status"] == "unknown" and b["status"] == "unknown":
                continue
            if "unknown" in (a["status"], b["status"]):
                verdict = "unknown"
            else:
                diff = SCORE[a["status"]] - SCORE[b["status"]]
                verdict = "lead" if diff > 0 else "behind" if diff < 0 else "even"
            tally[verdict] += 1
            rows.append({"name": cap["name"], "us": a, "them": b, "verdict": verdict})
        known = tally["lead"] + tally["even"] + tally["behind"]

        # Ratings on sites both have, plus sites only one has
        ra, rb = ratings_of(us), ratings_of(them)
        sites = [s for s in dict.fromkeys([*ra, *rb])]
        ratings = [{"site": s, "us": ra.get(s), "them": rb.get(s)} for s in sites]
        vals = [x["rating"] / x.get("out_of", 5) * 5 for x in [*ra.values(), *rb.values()]]
        lo = max(0.0, min(vals) - 0.5) if vals else 0.0
        lo = float(int(lo * 2) / 2)  # snap to .5 so the axis reads cleanly

        ids = _card_ids(card)
        indie = sum(1 for i in ids if i in by_id and not _origin(by_id[i]))
        cards.append({
            "rows": rows, "tally": tally, "known": known,
            "ratings": ratings, "axis_lo": lo,
            "evidence": {"total": len(ids), "independent": indie,
                         "pct": round(100 * indie / len(ids)) if ids else 0},
        })

    # Market overview: ratings table + capability grid for every company
    names = [us, *r["competitors"]]
    all_sites = list(dict.fromkeys(s for n in names for s in ratings_of(n)))
    market_ratings = [{"name": n, "by_site": ratings_of(n)} for n in names]
    return {"cards": cards, "names": names, "sites": all_sites, "market_ratings": market_ratings,
            "matrix": matrix}
```

In `intel/render.py`, delete that moved block and import it instead:

```python
from .domain.views import STATUS_LABEL, _origin, build_views  # noqa: F401  (render_html still uses these)
```

- [ ] **Step 4: Point callers at the domain modules**

In `intel/collect.py`: delete `NEWSWIRES`, `MARKET` and `classify_origin` definitions and add

```python
from .domain.origins import MARKET, NEWSWIRES, classify_origin  # noqa: F401
```

In `intel/analyze.py`: delete `origin_label`, `REVIEW_DOMAINS`, `number_in_text`, and replace the body of `Analyst._verify_ratings` with

```python
    def _verify_ratings(self, prof: CompanyProfile) -> None:
        """Ratings are numbers - keep only ones printed on an independent review-site page."""
        prof.ratings = verify_ratings(prof.ratings, self.verifier.by_id)
```

and change its imports to

```python
from .domain.origins import origin_label
from .domain.ratings import number_in_text, verify_ratings  # noqa: F401  (number_in_text re-exported for tests)
from .domain.verify import Verifier, VerifyStats
```

In `tests/test_pipeline.py` replace `from intel.verify import Verifier, quote_is_verbatim` with `from intel.domain.verify import Verifier, quote_is_verbatim`, and in `test_classify_origin_and_numbers` replace the two local imports with:

```python
    from intel.domain.origins import classify_origin
    from intel.domain.ratings import number_in_text
```

In `tests/test_golden.py` replace the import with:

```python
from intel.domain.views import build_views
from intel.render import render_markdown
```

- [ ] **Step 5: Run the whole suite**

Run: `cd apps/intel && uv run pytest -q && uv run ruff check .`
Expected: all tests PASS (including the three new `test_views.py` tests and both golden tests); ruff clean (fix import order with `uv run ruff check --fix .` if it reports `I001`).

- [ ] **Step 6: Commit**

```bash
git add -A apps/intel
git commit -m "refactor: extract evidence, ratings and scoring rules into intel.domain

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Split settings from companies in `config.py`

**Files:**
- Modify: `apps/intel/intel/config.py:80-144` (replace `load_config` and `_validate`), `apps/intel/intel/config.py` `Config` dataclass
- Test: `apps/intel/tests/test_config.py`

**Interfaces:**
- Produces:
  - `Config` gains fields `runs_per_day: int = 30`, `tavily_calls_per_day: int = 30`, `run_mode: str = "inline"`.
  - `default_env_file() -> Path` (repo-root `.env`, overridable by `INTEL_ENV_FILE`).
  - `load_settings(env_file: str | Path | None = None) -> Config` — keys/settings only, company fields empty, **does not validate**.
  - `settings_problem(cfg: Config) -> str | None` — the old `_validate` messages, returned instead of raised.
  - `with_companies(settings: Config, company: Company, competitors: list[Company], category: str = "") -> Config`.
  - `load_config(env_file=".env") -> Config` — unchanged behaviour for the CLI (validates, raises `SystemExit`).

- [ ] **Step 1: Write `tests/test_config.py`**

```python
from intel.config import Company, load_settings, settings_problem, with_companies


def test_load_settings_needs_no_companies(tmp_path, monkeypatch):
    for k in ("COMPANY", "COMPETITORS", "LLM_PROVIDER", "OPENROUTER_API_KEY", "RUNS_PER_DAY"):
        monkeypatch.delenv(k, raising=False)
    env = tmp_path / ".env"
    env.write_text("LLM_PROVIDER=openrouter\nRUNS_PER_DAY=5\n")
    s = load_settings(env)
    assert s.company.name == "" and s.competitors == [] and s.runs_per_day == 5
    assert "OPENROUTER_API_KEY" in settings_problem(s)


def test_with_companies_copies_company_objects():
    s = load_settings("/nonexistent")
    acme = Company("Acme", "acme.com")
    cfg = with_companies(s, acme, [Company("Rival")], "help desk")
    cfg.company.domain = "changed.com"
    assert acme.domain == "acme.com" and cfg.category == "help desk"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/intel && uv run pytest -q tests/test_config.py`
Expected: FAIL with `ImportError: cannot import name 'load_settings'`

- [ ] **Step 3: Implement**

Add to the `Config` dataclass (after `notes_dir`):

```python
    runs_per_day: int = 30
    tavily_calls_per_day: int = 30
    run_mode: str = "inline"  # "inline" (thread, local dev) | "queue" (Vercel Queues)
```

Add `from dataclasses import dataclass, field, replace` to the imports, then replace everything from `def load_config` to the end of the file with:

```python
def default_env_file() -> Path:
    """Repo-root .env (apps/intel/intel/config.py -> repo root), overridable by INTEL_ENV_FILE."""
    return Path(os.getenv("INTEL_ENV_FILE") or Path(__file__).resolve().parents[3] / ".env")


def load_settings(env_file: str | Path | None = None) -> Config:
    """API keys and tuning only - no companies, no validation (the API reports problems per request)."""
    path = Path(env_file) if env_file else default_env_file()
    if path.exists():
        load_dotenv(path, override=False)
    return Config(
        company=Company(""),
        competitors=[],
        llm_provider=os.getenv("LLM_PROVIDER", "anthropic").strip().lower(),
        llm_model=os.getenv("LLM_MODEL", "").strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "").strip(),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        search_provider=os.getenv("SEARCH_PROVIDER", "auto").strip().lower(),
        tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
        results_per_query=_int("RESULTS_PER_QUERY", 3),
        max_chars_per_source=_int("MAX_CHARS_PER_SOURCE", 6000),
        cache_ttl_hours=_float("CACHE_TTL_HOURS", 24),
        output_dir=Path(os.getenv("OUTPUT_DIR", "reports").strip() or "reports"),
        runs_per_day=_int("RUNS_PER_DAY", 30),
        tavily_calls_per_day=_int("TAVILY_CALLS_PER_DAY", 30),
        run_mode=os.getenv("RUN_MODE", "inline").strip().lower() or "inline",
    )


def with_companies(settings: Config, company: Company, competitors: list[Company], category: str = "") -> Config:
    return replace(
        settings,
        company=Company(company.name, company.domain),
        competitors=[Company(c.name, c.domain) for c in competitors],
        category=category,
    )


def load_config(env_file: str | None = ".env") -> Config:
    """CLI entry: settings + companies from .env, validated (raises SystemExit with a friendly message)."""
    settings = load_settings(env_file)
    company_name = os.getenv("COMPANY", "").strip()
    competitors_raw = os.getenv("COMPETITORS", "").strip()
    if not company_name:
        raise SystemExit("COMPANY is not set. Copy .env.example to .env and fill it in.")
    if not competitors_raw:
        raise SystemExit("COMPETITORS is not set (comma-separated list).")
    cfg = with_companies(
        settings,
        Company(company_name, clean_domain(os.getenv("COMPANY_DOMAIN"))),
        [parse_company(t) for t in competitors_raw.split(",") if t.strip()],
        os.getenv("CATEGORY", "").strip(),
    )
    if problem := settings_problem(cfg):
        raise SystemExit(problem)
    return cfg


def settings_problem(cfg: Config) -> str | None:
    if cfg.llm_provider not in ("anthropic", "openai", "openrouter"):
        return f"LLM_PROVIDER must be 'openrouter', 'anthropic' or 'openai', got '{cfg.llm_provider}'."
    if cfg.llm_provider == "openrouter" and not cfg.openrouter_api_key:
        return "LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is empty (get one free at openrouter.ai/keys)."
    if cfg.llm_provider == "anthropic" and not cfg.anthropic_api_key:
        hint = (
            " You've set OPENAI_API_KEY - if that's your Gemini/OpenAI/Groq key, set LLM_PROVIDER=openai."
            if cfg.openai_api_key else ""
        )
        return f"LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty.{hint}"
    if cfg.llm_provider == "openai" and not cfg.openai_api_key:
        return ("LLM_PROVIDER=openai but OPENAI_API_KEY is empty. "
                "(For Gemini/Groq, put that service's key in OPENAI_API_KEY.)")
    if cfg.llm_provider == "openai" and not cfg.openai_base_url and not cfg.openai_api_key.startswith("sk-"):
        return ("OPENAI_API_KEY doesn't look like an OpenAI key, and OPENAI_BASE_URL is empty, so the "
                "request would go to OpenAI and fail. For Gemini set:\n"
                "  OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/")
    if cfg.search_provider == "tavily" and not cfg.tavily_api_key:
        return "SEARCH_PROVIDER=tavily but TAVILY_API_KEY is empty."
    return None
```

- [ ] **Step 4: Run the whole suite**

Run: `cd apps/intel && uv run pytest -q`
Expected: all PASS (the existing end-to-end tests still call `load_config`).

- [ ] **Step 5: Commit**

```bash
git add -A apps/intel
git commit -m "refactor: separate settings from companies in config

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `Store` interface and a store-backed cache

**Files:**
- Create: `apps/intel/intel/store.py`
- Modify: `apps/intel/intel/cache.py` (rewrite), `apps/intel/intel/pipeline.py:58` (cache construction)
- Test: `apps/intel/tests/test_store.py`

**Interfaces:**
- Produces:
  - `class Store(Protocol)`: `get_json(key: str) -> dict | list | None`, `put_json(key: str, value) -> None`, `list_keys(prefix: str) -> list[str]`.
  - `LocalStore(root: Path)`, `MemoryStore()`.
  - `data_dir() -> Path` (`DATA_DIR` env or `apps/intel/data`), `make_store() -> Store` (Blob when `BLOB_READ_WRITE_TOKEN` is set — wired in Task 18; LocalStore otherwise).
  - `DiskCache(store: Store, ttl_hours: float, clock: Callable[[], float] = time.time)` with unchanged `get_or_set(namespace, key, fn)`.

- [ ] **Step 1: Write `tests/test_store.py`**

```python
import pytest

from intel.cache import DiskCache
from intel.store import LocalStore, MemoryStore


@pytest.mark.parametrize("make", [lambda p: LocalStore(p), lambda p: MemoryStore()])
def test_round_trip_and_list(tmp_path, make):
    s = make(tmp_path)
    assert s.get_json("runs/abc.json") is None
    s.put_json("runs/abc.json", {"a": 1})
    s.put_json("runs/def.json", {"b": 2})
    s.put_json("cache/x.json", [1])
    assert s.get_json("runs/abc.json") == {"a": 1}
    assert sorted(s.list_keys("runs/")) == ["runs/abc.json", "runs/def.json"]


def test_local_store_rejects_escaping_keys(tmp_path):
    s = LocalStore(tmp_path / "data")
    with pytest.raises(ValueError):
        s.put_json("../escape.json", {})
    with pytest.raises(ValueError):
        s.get_json("/etc/passwd")


def test_cache_respects_ttl_and_skips_empty():
    now = [1000.0]
    cache = DiskCache(MemoryStore(), ttl_hours=1, clock=lambda: now[0])
    calls = []
    fn = lambda: calls.append(1) or {"hits": 3}  # noqa: E731
    assert cache.get_or_set("search", {"q": "x"}, fn) == {"hits": 3}
    assert cache.get_or_set("search", {"q": "x"}, fn) == {"hits": 3}
    assert len(calls) == 1
    now[0] += 3601
    cache.get_or_set("search", {"q": "x"}, fn)
    assert len(calls) == 2
    assert cache.get_or_set("search", {"q": "empty"}, lambda: []) == []
    assert cache.store.get_json(cache._key("search", {"q": "empty"})) is None


def test_cache_disabled_when_ttl_zero():
    cache = DiskCache(MemoryStore(), ttl_hours=0)
    calls = []
    for _ in range(2):
        cache.get_or_set("s", "k", lambda: calls.append(1) or {"v": 1})
    assert len(calls) == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/intel && uv run pytest -q tests/test_store.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'intel.store'`

- [ ] **Step 3: Create `intel/store.py`**

```python
"""Where runs, caches and usage counters live: local files in dev, Vercel Blob when deployed.

Methods are synchronous; never call them from inside a running event loop."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol


class Store(Protocol):
    def get_json(self, key: str) -> Any | None: ...
    def put_json(self, key: str, value: Any) -> None: ...
    def list_keys(self, prefix: str) -> list[str]: ...


class LocalStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if key.startswith("/") or not p.is_relative_to(self.root):
            raise ValueError(f"Store key escapes the store: {key!r}")
        return p

    def get_json(self, key: str) -> Any | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return None

    def put_json(self, key: str, value: Any) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False))
        tmp.replace(p)  # atomic: readers never see a half-written file

    def list_keys(self, prefix: str) -> list[str]:
        base = self._path(prefix.rstrip("/")) if prefix.strip("/") else self.root
        if not base.exists():
            return []
        return [str(p.relative_to(self.root)) for p in base.rglob("*.json")]


class MemoryStore:
    """For tests."""

    def __init__(self):
        self.data: dict[str, str] = {}

    def get_json(self, key: str) -> Any | None:
        return json.loads(self.data[key]) if key in self.data else None

    def put_json(self, key: str, value: Any) -> None:
        self.data[key] = json.dumps(value)

    def list_keys(self, prefix: str) -> list[str]:
        return [k for k in self.data if k.startswith(prefix)]


def data_dir() -> Path:
    return Path(os.getenv("DATA_DIR") or Path(__file__).resolve().parents[1] / "data")


def make_store() -> Store:
    return LocalStore(data_dir())
```

- [ ] **Step 4: Rewrite `intel/cache.py`**

```python
"""Small cache for search results, pages and API calls, kept in the Store so it survives
between serverless invocations. Empty/failed results are never cached."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

from .store import Store


class DiskCache:
    def __init__(self, store: Store, ttl_hours: float, clock: Callable[[], float] = time.time):
        self.store = store
        self.ttl = ttl_hours * 3600
        self.enabled = ttl_hours > 0
        self.clock = clock

    def _key(self, namespace: str, key: Any) -> str:
        digest = hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()
        return f"cache/{namespace}/{digest}.json"

    def get_or_set(self, namespace: str, key: Any, fn: Callable[[], Any]) -> Any:
        k = self._key(namespace, key)
        if self.enabled:
            hit = self.store.get_json(k)
            if isinstance(hit, dict) and self.clock() - hit.get("saved_at", 0) < self.ttl:
                return hit.get("value")
        value = fn()
        if self.enabled and value:
            self.store.put_json(k, {"saved_at": self.clock(), "value": value})
        return value
```

- [ ] **Step 5: Keep the old pipeline working**

In `intel/pipeline.py` replace

```python
    cache = DiskCache(cfg.cache_dir, cfg.cache_ttl_hours if use_cache else 0)
```

with

```python
    cache = DiskCache(make_store(), cfg.cache_ttl_hours if use_cache else 0)
```

and add `from .store import make_store` to its imports.

- [ ] **Step 6: Run the whole suite**

Run: `cd apps/intel && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add -A apps/intel
git commit -m "feat: Store interface (local/memory) and store-backed cache

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Run requests, run IDs, run documents and the daily budget

**Files:**
- Create: `apps/intel/intel/runs.py`
- Test: `apps/intel/tests/test_runs.py`

**Interfaces:**
- Consumes: `Store` (Task 5), `clean_domain`, `Config` (Task 4).
- Produces:
  - `STAGES = ["collect", "profiles", "battlecards", "matrix", "positioning", "finalize"]`, `OPTIONAL_STAGES = {"matrix", "positioning"}`, `RUN_ID_PATTERN = r"^[0-9a-f]{10}$"`.
  - `CompanyIn(name: str, domain: str | None)`, `RunRequest(company: CompanyIn, competitors: list[CompanyIn], category: str = "")`.
  - `request_from_config(cfg: Config) -> RunRequest`, `company_key(req) -> str`, `run_id_for(req, day: str) -> str`, `run_key(run_id) -> str`, `now_iso() -> str`.
  - `new_run_doc(run_id, req, day) -> dict`, `mark(doc, stage, status, note="") -> None`.
  - `Budget(store, day)` with `.get() -> dict` and `.add(**increments) -> None`.
  - `CapacityError(RuntimeError)`, `create_run(store, req, *, day: str | None = None, featured=False, runs_per_day: int | None = None) -> tuple[dict, bool]`.

- [ ] **Step 1: Write `tests/test_runs.py`**

```python
import pytest
from pydantic import ValidationError

from intel.runs import (
    Budget, CapacityError, RunRequest, create_run, mark, new_run_doc, run_id_for, run_key,
)
from intel.store import MemoryStore


def req(**over):
    base = {"company": {"name": "Acme", "domain": "https://www.Acme.com/x"},
            "competitors": [{"name": "Rival"}, {"name": "Other"}], "category": "  help   desk "}
    base.update(over)
    return RunRequest(**base)


def test_request_normalises_inputs():
    r = req()
    assert r.company.domain == "acme.com" and r.category == "help desk"


@pytest.mark.parametrize("bad", [
    {"competitors": []},
    {"competitors": [{"name": f"C{i}"} for i in range(5)]},
    {"competitors": [{"name": "acme"}]},
    {"competitors": [{"name": "Rival"}, {"name": "rival"}]},
    {"company": {"name": "   "}},
    {"company": {"name": "x" * 61}},
])
def test_bad_requests_are_rejected(bad):
    with pytest.raises(ValidationError):
        req(**bad)


def test_run_id_is_stable_and_order_independent():
    a = run_id_for(req(), "2026-10-05")
    b = run_id_for(req(competitors=[{"name": "Other"}, {"name": "Rival"}]), "2026-10-05")
    assert a == b and len(a) == 10
    assert a != run_id_for(req(), "2026-10-06")
    swapped = req(company={"name": "Rival"}, competitors=[{"name": "Acme"}, {"name": "Other"}])
    assert run_id_for(swapped, "2026-10-05") != a  # who "we" are matters


def test_create_run_reuses_same_day_request():
    store = MemoryStore()
    doc, reused = create_run(store, req(), day="2026-10-05")
    assert not reused and doc["status"] == "queued"
    again, reused = create_run(store, req(), day="2026-10-05")
    assert reused and again["id"] == doc["id"]
    assert Budget(store, "2026-10-05").get()["runs"] == 1


def test_failed_run_can_be_retried_same_day():
    store = MemoryStore()
    doc, _ = create_run(store, req(), day="2026-10-05")
    doc["status"] = "failed"
    store.put_json(run_key(doc["id"]), doc)
    again, reused = create_run(store, req(), day="2026-10-05")
    assert not reused and again["status"] == "queued"


def test_daily_cap():
    store = MemoryStore()
    create_run(store, req(), day="2026-10-05", runs_per_day=1)
    with pytest.raises(CapacityError):
        create_run(store, req(category="other"), day="2026-10-05", runs_per_day=1)


def test_mark_replaces_stage_entry():
    doc = new_run_doc("0123456789", req(), "2026-10-05")
    mark(doc, "collect", "running")
    mark(doc, "collect", "done", "45 sources")
    assert [(p["stage"], p["status"], p["note"]) for p in doc["progress"]] == [("collect", "done", "45 sources")]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/intel && uv run pytest -q tests/test_runs.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'intel.runs'`

- [ ] **Step 3: Create `intel/runs.py`**

```python
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
```

- [ ] **Step 4: Run tests**

Run: `cd apps/intel && uv run pytest -q tests/test_runs.py`
Expected: 7 tests PASS (12 with parametrization).

- [ ] **Step 5: Commit**

```bash
git add -A apps/intel
git commit -m "feat: run requests, deterministic run IDs, run documents and daily budget

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Stages, runner, LLM time budget — replace `pipeline.py`

**Files:**
- Create: `apps/intel/intel/stages.py`, `apps/intel/intel/runner.py`, `apps/intel/tests/conftest.py`, `apps/intel/tests/test_runner.py`
- Modify: `apps/intel/intel/llm.py` (deadline), `apps/intel/intel/search.py` (count API calls), `apps/intel/run.py` (CLI on the runner)
- Rename: `apps/intel/intel/render.py` → `apps/intel/intel/render_md.py` (Markdown only)
- Delete: `apps/intel/intel/pipeline.py`, `apps/intel/intel/templates/`, the end-to-end tests in `tests/test_pipeline.py` (moved to `test_runner.py`)

**Interfaces:**
- Consumes: Tasks 3–6.
- Produces:
  - `stages.Deps(make_search: Callable[[Config, DiskCache], SearchProvider], make_llm: Callable[[Config], LLM])`.
  - `stages.StageContext`, `stages.load_notes(cfg) -> dict[str, str]`, stage functions `collect/profiles/battlecards/matrix/positioning/finalize(ctx) -> str | None` (returned string = progress note).
  - `runner.MAX_ATTEMPTS = 3`, `runner.STAGE_BUDGET_SECONDS = 240`.
  - `runner.config_for(settings: Config, doc: dict) -> Config`.
  - `runner.run_stage(store, settings, run_id, stage, *, deps=None, attempt=1) -> str | None` (next stage, or `None` when the run is finished/failed).
  - `runner.run_all(store, settings, run_id, *, deps=None) -> dict`.
  - `LLM.deadline: float | None` (a `time.monotonic()` timestamp).
  - `SearchProvider.api_calls: int`.
  - `render_md.render_markdown(r: dict) -> str`.

- [ ] **Step 1: Move the fakes into `tests/conftest.py`**

Cut `PRICING`, `REVIEW`, `FakeSearch` and `FakeLLM` from `tests/test_pipeline.py` and paste them into a new `tests/conftest.py`, then add below them:

```python
import pytest

from intel.stages import Deps
from intel.store import MemoryStore

FAKE_DEPS = Deps(make_search=lambda cfg, cache: FakeSearch(cache, 3), make_llm=FakeLLM)


@pytest.fixture
def offline(monkeypatch):
    """No network: page fetches and keyless APIs return nothing."""
    monkeypatch.setattr("intel.collect.fetch_page", lambda url, cache: "")
    monkeypatch.setattr("intel.collect.fetch_json", lambda url, cache, params=None: None)


@pytest.fixture
def store():
    return MemoryStore()
```

Add a class-level call counter to `FakeLLM` (first lines of the class body and of `structured`):

```python
class FakeLLM:
    calls: list[str] = []  # schema names, across all instances; reset per test
    fail_for: set[str] = set()  # company names whose CompanyProfile call raises once

    def structured(self, system, prompt, schema, max_tokens=8000):
        import re

        FakeLLM.calls.append(schema.__name__)
        for name in list(FakeLLM.fail_for):
            if schema.__name__ == "CompanyProfile" and f"**{name}**" in prompt:
                FakeLLM.fail_for.discard(name)
                raise RuntimeError(f"flaky model for {name}")
        self.usage["calls"] += 1
```

(the rest of `structured` stays as it is). Also add `FakeLLM.calls.clear()` and `FakeLLM.fail_for.clear()` to the `store` fixture body before `return`.

- [ ] **Step 2: Write `tests/test_runner.py`**

```python
import json
from datetime import date

from conftest import FAKE_DEPS, FakeLLM

from intel.config import load_config
from intel.render_md import render_markdown
from intel.runner import MAX_ATTEMPTS, run_all, run_stage
from intel.runs import create_run, request_from_config, run_key


def write_env(tmp_path, monkeypatch):
    for k in ("COMPANY", "COMPANY_DOMAIN", "COMPETITORS", "CATEGORY", "LLM_PROVIDER", "SEARCH_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    env = tmp_path / "test.env"
    env.write_text("COMPANY=Acme\nCOMPETITORS=Rival, Other:other.io\nCATEGORY=help desk software\n"
                   "LLM_PROVIDER=anthropic\nANTHROPIC_API_KEY=test\nSEARCH_PROVIDER=ddg\nCACHE_TTL_HOURS=0\n")
    cfg = load_config(str(env))
    cfg.notes_dir = tmp_path / "notes"
    return cfg


def start(store, cfg, day=None):
    doc, _ = create_run(store, request_from_config(cfg), day=day)
    return doc["id"]


def test_full_run_produces_verified_report(tmp_path, monkeypatch, offline, store):
    cfg = write_env(tmp_path, monkeypatch)
    cfg.notes_dir.mkdir()
    (cfg.notes_dir / "rival.md").write_text("Rival's partner channel is **underrated**.")
    doc = run_all(store, cfg, start(store, cfg), deps=FAKE_DEPS)

    assert doc["status"] == "succeeded" and doc["stages_done"][-1] == "finalize"
    assert doc["company"] == "Acme" and doc["competitors"] == ["Rival", "Other"]
    assert doc["profiles"]["Rival"]["domain"] == "rival.com"
    assert doc["profiles"]["Other"]["domain"] == "other.io"
    assert doc["stats"]["claims_dropped"] == 3 and doc["stats"]["quotes_dropped"] == 3
    assert all(len(p["quotes"]) == 1 for p in doc["profiles"].values())
    assert [x["site"] for x in doc["profiles"]["Rival"]["ratings"]] == ["G2"]
    caps = doc["matrix"]["capabilities"]
    assert [c["name"] for c in caps] == ["Reporting"]
    assert [c["status"] for c in caps[0]["cells"]] == ["full", "partial", "unknown"]
    assert {"independent", "vendor:Rival"} <= {s["origin"] for s in doc["sources"]}
    assert doc["views"]["cards"][0]["evidence"]["total"] >= 1
    assert doc["notes"]["Rival"].startswith("Rival's partner")
    assert doc["changes"] is None
    assert render_markdown(doc).startswith("# Competitive intelligence: Acme")


def test_second_run_reports_changes(tmp_path, monkeypatch, offline, store):
    cfg = write_env(tmp_path, monkeypatch)
    run_all(store, cfg, start(store, cfg, day="2000-01-01"), deps=FAKE_DEPS)
    doc = run_all(store, cfg, start(store, cfg, day=date.today().isoformat()), deps=FAKE_DEPS)
    assert doc["previous_run"] == "2000-01-01"
    assert doc["changes"]["changes"][0]["severity"] == "high"


def test_finished_stage_is_not_rerun(tmp_path, monkeypatch, offline, store):
    cfg = write_env(tmp_path, monkeypatch)
    run_id = start(store, cfg)
    run_all(store, cfg, run_id, deps=FAKE_DEPS)
    before = len(FakeLLM.calls)
    assert run_stage(store, cfg, run_id, "profiles", deps=FAKE_DEPS) is None  # run already finished
    doc = store.get_json(run_key(run_id))
    doc["status"] = "running"  # pretend a duplicate queue delivery arrives mid-run
    store.put_json(run_key(run_id), doc)
    assert run_stage(store, cfg, run_id, "profiles", deps=FAKE_DEPS) == "battlecards"
    assert len(FakeLLM.calls) == before


def test_stage_resumes_without_redoing_finished_items(tmp_path, monkeypatch, offline, store):
    cfg = write_env(tmp_path, monkeypatch)
    run_id = start(store, cfg)
    assert run_stage(store, cfg, run_id, "collect", deps=FAKE_DEPS) == "profiles"
    FakeLLM.fail_for = {"Rival"}
    try:
        run_stage(store, cfg, run_id, "profiles", deps=FAKE_DEPS, attempt=1)
        raise AssertionError("expected the flaky profile to raise")
    except Exception as e:  # noqa: BLE001
        assert "Rival" in str(e)
    done = set(store.get_json(run_key(run_id))["profiles"])
    assert done == {"Acme", "Other"}
    FakeLLM.calls.clear()
    assert run_stage(store, cfg, run_id, "profiles", deps=FAKE_DEPS, attempt=2) == "battlecards"
    assert FakeLLM.calls == ["CompanyProfile"]  # only Rival was redone


def test_required_stage_fails_after_max_attempts(tmp_path, monkeypatch, offline, store):
    cfg = write_env(tmp_path, monkeypatch)
    run_id = start(store, cfg)
    run_stage(store, cfg, run_id, "collect", deps=FAKE_DEPS)
    FakeLLM.fail_for = {"Rival"}
    assert run_stage(store, cfg, run_id, "profiles", deps=FAKE_DEPS, attempt=MAX_ATTEMPTS) is None
    doc = store.get_json(run_key(run_id))
    assert doc["status"] == "failed" and "profiles" in doc["error"]


def test_optional_stage_failure_makes_run_partial(tmp_path, monkeypatch, offline, store):
    cfg = write_env(tmp_path, monkeypatch)

    class NoMatrix(FakeLLM):
        def structured(self, system, prompt, schema, max_tokens=8000):
            if schema.__name__ == "CapabilityMatrix":
                raise RuntimeError("model down")
            return super().structured(system, prompt, schema, max_tokens)

    from intel.stages import Deps
    deps = Deps(make_search=FAKE_DEPS.make_search, make_llm=NoMatrix)
    doc = run_all(store, cfg, start(store, cfg), deps=deps)
    assert doc["status"] == "partial" and doc["matrix"] is None
    assert any(p["stage"] == "matrix" and p["status"] == "skipped" for p in doc["progress"])
    assert json.dumps(doc)  # still serialisable
```

Delete `test_full_run_produces_verified_reports`, `test_second_run_reports_changes`, the `env` fixture and the now-unused imports from `tests/test_pipeline.py` (the unit tests for config, JSON extraction, quotes, verifier, bias rules and origins stay).

Add to `tests/test_llm.py`:

```python
def test_expired_deadline_stops_without_calling_the_model():
    llm, called = bare_llm(), []
    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: called.append(kw))))
    llm.deadline = time.monotonic() - 1
    with pytest.raises(LLMError):
        llm.structured("sys", "prompt", Thing)
    assert called == []
```

- [ ] **Step 3: Run to verify failure**

Run: `cd apps/intel && uv run pytest -q tests/test_runner.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'intel.stages'`

- [ ] **Step 4: Add the LLM time budget (`intel/llm.py`)**

In `LLM.__init__`, add as the first statement after `self.provider = cfg.llm_provider`:

```python
        self.deadline: float | None = None  # time.monotonic() by which the current stage must finish
```

Add these methods to `LLM` (above `_complete`):

```python
    def _remaining(self) -> float | None:
        return None if self.deadline is None else self.deadline - time.monotonic()

    def _apply_deadline(self, kwargs: dict) -> None:
        """Never let one model call outlive the stage's function time limit."""
        rem = self._remaining()
        if rem is None:
            return
        if rem < 15:
            raise TransientLLMError("This stage's time budget is used up")
        kwargs["timeout"] = rem - 5

    def _wait_seconds(self, wanted: float) -> float:
        rem = self._remaining()
        return wanted if rem is None else max(0.0, min(wanted, rem - 20))
```

In `_complete`, in the Anthropic branch build the call as a dict so the deadline applies:

```python
        if self.provider == "anthropic":
            kwargs = dict(model=self.model, system=system, messages=messages, max_tokens=max_tokens, temperature=0.2)
            self._apply_deadline(kwargs)
            resp = self._client.messages.create(**kwargs)
```

In the OpenAI-compatible branch, call `self._apply_deadline(kwargs)` immediately before `try:` / `resp = self._create_with_rate_limit_wait(kwargs)`.

In `_create_with_rate_limit_wait`, replace `time.sleep(60)` with:

```python
                wait = self._wait_seconds(60)
                if wait <= 0:
                    raise TransientLLMError("Rate limited and out of stage time") from e
                time.sleep(wait)
```

- [ ] **Step 5: Count real search API calls (`intel/search.py`)**

In `SearchProvider.__init__` add `self.api_calls = 0`. In `TavilySearch._search` and `DuckDuckGoSearch._search`, add `self.api_calls += 1` as the first line of the method body (these only run on cache misses).

- [ ] **Step 6: Markdown-only renderer**

```bash
cd apps/intel
git mv intel/render.py intel/render_md.py
git rm -r -q intel/templates
```

In `intel/render_md.py`: delete `render_html`, the `jinja2`, `markupsafe` and `TEMPLATES` imports/definitions, and change the docstring to `"""Renders a report as GitHub-friendly Markdown."""`. Keep `render_markdown` and its import `from .domain.views import build_views`. Remove `"jinja2>=3.1",` from `pyproject.toml` and `requirements.txt`. Update `tests/test_golden.py`: `from intel.render_md import render_markdown`.

- [ ] **Step 7: Create `intel/stages.py`**

```python
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
    sources, facts = collect_sources(cfg, search, ctx.cache)
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
```

- [ ] **Step 8: Create `intel/runner.py`**

```python
"""Runs stages: one at a time (queue consumer) or all in a row (CLI, local dev, tests)."""
from __future__ import annotations

import logging
import time

from .config import Company, Config, with_companies
from .runs import OPTIONAL_STAGES, STAGES, RunRequest, mark, run_key
from .stages import STAGE_FUNCS, Deps, StageContext
from .store import Store

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
STAGE_BUDGET_SECONDS = 240  # Vercel Hobby functions stop at 300s
FINISHED = ("succeeded", "partial", "failed")


def config_for(settings: Config, doc: dict) -> Config:
    req = RunRequest(**doc["inputs"])
    domains = doc.get("domains") or {}

    def co(c) -> Company:
        return Company(c.name, domains.get(c.name) or c.domain)

    return with_companies(settings, co(req.company), [co(c) for c in req.competitors], req.category)


def next_stage(stage: str) -> str | None:
    i = STAGES.index(stage)
    return STAGES[i + 1] if i + 1 < len(STAGES) else None


def run_stage(store: Store, settings: Config, run_id: str, stage: str, *, deps: Deps | None = None,
              attempt: int = 1) -> str | None:
    """Run one stage. Returns the next stage to run, or None when the run is finished or failed.
    Raises on a retryable failure (the caller - queue or run_all - retries)."""
    doc = store.get_json(run_key(run_id))
    if doc is None:
        raise KeyError(f"Unknown run {run_id}")
    if doc["status"] in FINISHED:
        return None
    if stage in doc["stages_done"]:
        return next_stage(stage)  # duplicate delivery: nothing to do

    ctx = StageContext(cfg=config_for(settings, doc), store=store, doc=doc, deps=deps or Deps(),
                       deadline=time.monotonic() + STAGE_BUDGET_SECONDS)
    doc["status"], doc["current_stage"] = "running", stage
    mark(doc, stage, "running")
    ctx.save()
    try:
        note = STAGE_FUNCS[stage](ctx) or ""
        mark(doc, stage, "done", note)
    except Exception as e:  # noqa: BLE001
        msg = f"{type(e).__name__}: {e}"[:400]
        log.warning("Run %s stage %s attempt %d failed: %s", run_id, stage, attempt, msg)
        if stage in OPTIONAL_STAGES:
            mark(doc, stage, "skipped", msg)
        elif attempt >= MAX_ATTEMPTS:
            mark(doc, stage, "failed", msg)
            doc["status"], doc["error"] = "failed", f"The {stage} step failed: {msg}"
            ctx.save()
            return None
        else:
            mark(doc, stage, "retrying", msg)
            ctx.save()
            raise
    doc["stages_done"].append(stage)
    ctx.save()
    return next_stage(stage)


def run_all(store: Store, settings: Config, run_id: str, *, deps: Deps | None = None) -> dict:
    stage: str | None = STAGES[0]
    while stage:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                stage = run_stage(store, settings, run_id, stage, deps=deps, attempt=attempt)
                break
            except Exception:  # noqa: BLE001 - run_stage already recorded it; retry
                continue
    return store.get_json(run_key(run_id))
```

- [ ] **Step 9: Point the CLI at the runner (`apps/intel/run.py`)**

Replace the `main` function and the argparse block's `--no-diff`/`--rerender` lines:

```python
def main(args) -> None:
    from intel.config import load_config
    from intel.render_md import render_markdown
    from intel.runner import run_all
    from intel.runs import create_run, request_from_config
    from intel.store import data_dir, make_store

    if not Path(args.env).exists():
        raise SystemExit(f"Config file {args.env} not found. Copy .env.example to .env and fill it in.")
    cfg = load_config(args.env)
    if args.fresh:
        cfg.cache_ttl_hours = 0
    store = make_store()
    doc, reused = create_run(store, request_from_config(cfg))
    if doc["status"] not in ("succeeded", "partial"):
        doc = run_all(store, cfg, doc["id"])
    if doc["status"] == "failed":
        raise SystemExit(doc["error"])
    out = data_dir() / "exports" / f"{doc['id']}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(doc))
    print(f"\nRun {doc['id']} {'(reused from earlier today)' if reused else ''}: {doc['status']}\n  {out}")
```

and keep only these arguments:

```python
    ap.add_argument("--env", default=str(ROOT.parents[1] / ".env"), help="config file (default: repo-root .env)")
    ap.add_argument("--fresh", action="store_true", help="bypass the search/page cache")
    ap.add_argument("-v", "--verbose", action="store_true")
```

Update the module docstring's usage lines to `python run.py`, `python run.py --env acme.env`, `python run.py --fresh`.

- [ ] **Step 10: Delete the old pipeline and run everything**

```bash
cd apps/intel
git rm -q intel/pipeline.py
uv sync
uv run pytest -q && uv run ruff check .
```

Expected: all PASS (runner tests, golden tests unchanged, unit tests); ruff clean.

- [ ] **Step 11: Commit**

```bash
git add -A apps/intel
git commit -m "feat: resumable research stages and runner; LLM stage time budget

Replaces the one-shot pipeline. Each stage is idempotent at item level and
fits the 300s function limit. CLI now runs on the runner and writes Markdown.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Seed featured runs from POC snapshots

**Files:**
- Create: `apps/intel/intel/seed.py`
- Test: `apps/intel/tests/test_seed.py`

**Interfaces:**
- Consumes: `new_run_doc`, `run_id_for`, `mark`, `STAGES`, `build_views`, `make_store`.
- Produces: `import_snapshot(store, snapshot: dict, *, featured=True) -> str` (run id); CLI `uv run python -m intel.seed PATH [PATH ...]` printing one run id per line.

- [ ] **Step 1: Write `tests/test_seed.py`**

```python
import json
from pathlib import Path

from intel.runs import run_key
from intel.seed import import_snapshot
from intel.store import MemoryStore

FX = Path(__file__).parent / "fixtures"


def test_import_snapshot_creates_featured_finished_run():
    store = MemoryStore()
    snap = json.loads((FX / "netchex_snapshot.json").read_text())
    run_id = import_snapshot(store, snap)
    doc = store.get_json(run_key(run_id))
    assert doc["status"] == "succeeded" and doc["featured"] is True
    assert doc["company"] == "Netchex" and doc["competitors"] == ["Paylocity", "isolved", "Paycor"]
    assert len(doc["battlecards"]) == 3 and doc["views"]["cards"]
    assert doc["stats"]["vendor_quotes_dropped"] == snap["stats"]["vendor_quotes_dropped"]
    assert [p["status"] for p in doc["progress"]] == ["done"] * 6
    assert import_snapshot(store, snap) == run_id  # idempotent
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/intel && uv run pytest -q tests/test_seed.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'intel.seed'`

- [ ] **Step 3: Create `intel/seed.py`**

```python
"""Import POC snapshot.json files as featured runs, so the demo has content on day one.

    uv run python -m intel.seed tests/fixtures/netchex_snapshot.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .domain.views import build_views
from .runs import STAGES, CompanyIn, RunRequest, mark, new_run_doc, run_id_for, run_key
from .store import Store, make_store

COPY = ("model", "search_provider", "previous_run", "facts", "sources", "profiles", "battlecards",
        "matrix", "positioning", "changes", "notes")


def import_snapshot(store: Store, snapshot: dict, *, featured: bool = True) -> str:
    profiles = snapshot.get("profiles") or {}

    def ci(name: str) -> CompanyIn:
        return CompanyIn(name=name, domain=(profiles.get(name) or {}).get("domain"))

    req = RunRequest(company=ci(snapshot["company"]), competitors=[ci(n) for n in snapshot["competitors"]],
                     category=snapshot.get("category") or "")
    day = snapshot["run_date"]
    run_id = run_id_for(req, day)
    doc = new_run_doc(run_id, req, day)
    for k in COPY:
        if snapshot.get(k) is not None:
            doc[k] = snapshot[k]
    doc["stats"] = {**doc["stats"], **(snapshot.get("stats") or {})}
    doc["usage"] = {**doc["usage"], **(snapshot.get("usage") or {})}
    doc["domains"] = {n: p.get("domain") for n, p in profiles.items()}
    doc.update(status="succeeded", featured=featured, stages_done=list(STAGES), created_at=f"{day}T00:00:00+00:00")
    for stage in STAGES:
        mark(doc, stage, "done", "Imported from an earlier run")
    doc["views"] = build_views(doc)
    store.put_json(run_key(run_id), doc)
    return run_id


def main() -> None:
    ap = argparse.ArgumentParser(description="Import snapshot.json files as featured runs.")
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args()
    store = make_store()
    for p in args.paths:
        print(import_snapshot(store, json.loads(p.read_text())))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `cd apps/intel && uv run pytest -q tests/test_seed.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A apps/intel
git commit -m "feat: seed featured runs from POC snapshots

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Milestone M2 — The intel service

### Task 9: FastAPI `/v1` API with typed responses and an inline dispatcher

**Files:**
- Create: `apps/intel/intel/api_models.py`, `apps/intel/intel/dispatch.py`, `apps/intel/intel/api.py`
- Modify: `apps/intel/pyproject.toml` (add `fastapi`, `uvicorn`, `httpx`)
- Test: `apps/intel/tests/test_api.py`

**Interfaces:**
- Consumes: runs/runner/seed/store/config from Tasks 4–8.
- Produces:
  - `create_app(*, store=None, settings=None, deps=None, dispatcher=None) -> FastAPI`; module-level `app = create_app()` (lazy: loads settings/store on first request).
  - Dispatchers: `InlineDispatcher(store, settings, deps=None)` (background thread) and `SyncDispatcher(store, settings, deps=None)` (tests); both expose `start(run_id: str) -> None`. `make_dispatcher(settings, store) -> Dispatcher`.
  - Response models (OpenAPI schema names): `CreateRunOut`, `RunStatusOut`, `ProgressItem`, `RunSummary`, `SourceOut`, `CompanyFacts`, `CellView`, `CapabilityView`, `CapRow`, `Tally`, `RatingPair`, `Evidence`, `CardView`, `MarketRating`, `Views`, `ReportOut`.
  - Endpoints: `POST /v1/runs` (202; 400-style 422 on bad body; 429 at cap; 503 if LLM not configured), `GET /v1/runs`, `GET /v1/runs/{run_id}`, `GET /v1/runs/{run_id}/report` (409 if unfinished), `GET /v1/runs/{run_id}/export.md`, `GET /health`.

- [ ] **Step 1: Add dependencies**

Run: `cd apps/intel && uv add "fastapi>=0.115" "uvicorn[standard]>=0.30" && uv add --dev "httpx>=0.27"`

- [ ] **Step 2: Write `tests/test_api.py`**

```python
import json
from pathlib import Path

import pytest
from conftest import FAKE_DEPS
from fastapi.testclient import TestClient

from intel.api import create_app
from intel.config import load_settings
from intel.dispatch import SyncDispatcher
from intel.seed import import_snapshot

FX = Path(__file__).parent / "fixtures"
BODY = {"company": {"name": "Acme", "domain": "acme.com"}, "competitors": [{"name": "Rival"}], "category": "help desk"}


@pytest.fixture
def client(store, offline, monkeypatch):
    for k in ("LLM_PROVIDER", "SEARCH_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("SEARCH_PROVIDER", "ddg")
    settings = load_settings("/nonexistent")
    settings.cache_ttl_hours = 0
    app = create_app(store=store, settings=settings, deps=FAKE_DEPS,
                     dispatcher=SyncDispatcher(store, settings, FAKE_DEPS))
    return TestClient(app)


def test_create_run_and_fetch_report(client):
    r = client.post("/v1/runs", json=BODY)
    assert r.status_code == 202, r.text
    run_id = r.json()["run_id"]
    status = client.get(f"/v1/runs/{run_id}").json()
    assert status["status"] == "succeeded" and [p["stage"] for p in status["progress"]][-1] == "finalize"
    report = client.get(f"/v1/runs/{run_id}/report").json()
    assert report["company"] == "Acme" and report["battlecards"][0]["competitor"] == "Rival"
    assert "content" not in report["sources"][0]
    assert report["views"]["cards"][0]["evidence"]["total"] >= 1
    assert client.get(f"/v1/runs/{run_id}/export.md").text.startswith("# Competitive intelligence: Acme")


def test_create_run_reused_flag(client):
    first = client.post("/v1/runs", json=BODY).json()
    second = client.post("/v1/runs", json=BODY).json()
    assert second["run_id"] == first["run_id"] and second["reused"] is True


def test_bad_input_is_rejected(client):
    bad = {**BODY, "competitors": [{"name": "acme"}]}
    assert client.post("/v1/runs", json=bad).status_code == 422


def test_unknown_and_malformed_run_ids(client):
    assert client.get("/v1/runs/0000000000").status_code == 404
    assert client.get("/v1/runs/..%2Fescape").status_code in (404, 422)
    assert client.get("/v1/runs/NOT-HEX-ID").status_code == 422


def test_capacity_limit_returns_429(client, store):
    client.app.state.ctx.settings.runs_per_day = 0
    assert client.post("/v1/runs", json=BODY).status_code == 429


def test_missing_llm_config_returns_503(client):
    client.app.state.ctx.settings.anthropic_api_key = ""
    r = client.post("/v1/runs", json=BODY)
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_gallery_lists_featured_seeded_run(client, store):
    run_id = import_snapshot(store, json.loads((FX / "netchex_snapshot.json").read_text()))
    items = client.get("/v1/runs", params={"featured": True}).json()
    assert [i["id"] for i in items] == [run_id]
    report = client.get(f"/v1/runs/{run_id}/report").json()
    assert len(report["views"]["cards"]) == 3
```

- [ ] **Step 3: Run to verify failure**

Run: `cd apps/intel && uv run pytest -q tests/test_api.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'intel.api'`

- [ ] **Step 4: Create `intel/api_models.py`**

```python
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
```

- [ ] **Step 5: Create `intel/dispatch.py`**

```python
"""How a new run gets processed: a background thread locally, Vercel Queues in production."""
from __future__ import annotations

import logging
import threading
from typing import Protocol

from .config import Config
from .runner import run_all
from .stages import Deps
from .store import Store

log = logging.getLogger(__name__)


class Dispatcher(Protocol):
    def start(self, run_id: str) -> None: ...


class SyncDispatcher:
    """Runs everything before returning. Tests only."""

    def __init__(self, store: Store, settings: Config, deps: Deps | None = None):
        self.store, self.settings, self.deps = store, settings, deps

    def start(self, run_id: str) -> None:
        run_all(self.store, self.settings, run_id, deps=self.deps)


class InlineDispatcher(SyncDispatcher):
    """Local development: process the run in a daemon thread of the API process."""

    def start(self, run_id: str) -> None:
        def work():
            try:
                run_all(self.store, self.settings, run_id, deps=self.deps)
            except Exception:  # noqa: BLE001
                log.exception("Run %s crashed", run_id)

        threading.Thread(target=work, name=f"run-{run_id}", daemon=True).start()


def make_dispatcher(settings: Config, store: Store) -> Dispatcher:
    return InlineDispatcher(store, settings)
```

- [ ] **Step 6: Create `intel/api.py`**

```python
"""Private HTTP API for the web app. Not publicly routed on Vercel.

    uv run uvicorn intel.api:app --port 8000
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import PlainTextResponse

from .api_models import CreateRunOut, ReportOut, RunStatusOut, RunSummary
from .config import load_settings, settings_problem
from .dispatch import make_dispatcher
from .render_md import render_markdown
from .runs import RUN_ID_PATTERN, CapacityError, RunRequest, create_run, run_key
from .store import make_store

log = logging.getLogger(__name__)
RunId = Annotated[str, Path(pattern=RUN_ID_PATTERN)]
DONE = ("succeeded", "partial")


def create_app(*, store=None, settings=None, deps=None, dispatcher=None) -> FastAPI:
    app = FastAPI(title="Battlecard intel API", version="1.0.0", separate_input_output_schemas=False)
    ctx = SimpleNamespace(store=store, settings=settings, deps=deps, dispatcher=dispatcher)
    app.state.ctx = ctx

    def get_settings():
        if ctx.settings is None:
            ctx.settings = load_settings()
        return ctx.settings

    def get_store():
        if ctx.store is None:
            ctx.store = make_store()
        return ctx.store

    def get_dispatcher():
        if ctx.dispatcher is None:
            ctx.dispatcher = make_dispatcher(get_settings(), get_store())
        return ctx.dispatcher

    def load(run_id: str) -> dict:
        doc = get_store().get_json(run_key(run_id))
        if doc is None:
            raise HTTPException(404, "No run with that id")
        return doc

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/v1/runs", status_code=202, response_model=CreateRunOut)
    def start_run(req: RunRequest) -> CreateRunOut:
        settings = get_settings()
        if problem := settings_problem(settings):
            raise HTTPException(503, f"Research is unavailable: {problem}")
        try:
            doc, reused = create_run(get_store(), req, runs_per_day=settings.runs_per_day)
        except CapacityError as e:
            raise HTTPException(429, str(e)) from e
        if not reused:
            get_dispatcher().start(doc["id"])
            doc = load(doc["id"])
        return CreateRunOut(run_id=doc["id"], status=doc["status"], reused=reused)

    @app.get("/v1/runs", response_model=list[RunSummary])
    def list_runs(featured: bool = False, limit: Annotated[int, Query(ge=1, le=50)] = 20) -> list[RunSummary]:
        docs = [d for k in get_store().list_keys("runs/") if (d := get_store().get_json(k))]
        docs = [d for d in docs if d.get("status") in DONE and (d.get("featured") or not featured)]
        docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        return [RunSummary(**d) for d in docs[:limit]]

    @app.get("/v1/runs/{run_id}", response_model=RunStatusOut)
    def get_status(run_id: RunId) -> RunStatusOut:
        return RunStatusOut(**load(run_id))

    @app.get("/v1/runs/{run_id}/report", response_model=ReportOut)
    def get_report(run_id: RunId) -> ReportOut:
        doc = load(run_id)
        if doc["status"] not in DONE:
            raise HTTPException(409, "This run has not finished yet")
        sources = [{k: v for k, v in s.items() if k != "content"} for s in doc["sources"]]
        return ReportOut(**{**doc, "sources": sources, "positioning": doc.get("positioning") or None})

    @app.get("/v1/runs/{run_id}/export.md", response_class=PlainTextResponse)
    def export_md(run_id: RunId) -> str:
        doc = load(run_id)
        if doc["status"] not in DONE:
            raise HTTPException(409, "This run has not finished yet")
        return render_markdown(doc)

    return app


app = create_app()
```

- [ ] **Step 7: Run tests**

Run: `cd apps/intel && uv run pytest -q && uv run ruff check .`
Expected: all PASS.

- [ ] **Step 8: Smoke-test the real server**

```bash
cd apps/intel
DATA_DIR=/tmp/intel-smoke uv run python -m intel.seed tests/fixtures/netchex_snapshot.json
DATA_DIR=/tmp/intel-smoke uv run uvicorn intel.api:app --port 8000 &
sleep 3 && curl -s "localhost:8000/v1/runs?featured=true" | head -c 300; echo
kill %1
```

Expected: a JSON array containing one run with `"company":"Netchex"`.

- [ ] **Step 9: Commit**

```bash
git add -A apps/intel
git commit -m "feat: FastAPI /v1 API with typed report contract and inline dispatcher

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: OpenAPI contract export and drift check

**Files:**
- Create: `apps/intel/scripts/export_openapi.py`, `packages/contracts/openapi.json` (generated)
- Test: `apps/intel/tests/test_contract.py`

**Interfaces:**
- Produces: `packages/contracts/openapi.json`; `uv run python scripts/export_openapi.py [--check]` (exit 1 if the committed file is stale).

- [ ] **Step 1: Write `tests/test_contract.py`**

```python
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_committed_openapi_is_up_to_date():
    r = subprocess.run([sys.executable, "scripts/export_openapi.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/intel && uv run pytest -q tests/test_contract.py`
Expected: FAIL (script does not exist).

- [ ] **Step 3: Create `scripts/export_openapi.py`**

```python
"""Write (or --check) packages/contracts/openapi.json from the FastAPI app."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from intel.api import create_app  # noqa: E402

OUT = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "openapi.json"


def main() -> int:
    spec = json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != spec:
            print(f"{OUT} is stale - run: uv run python scripts/export_openapi.py")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(spec)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Generate and test**

Run: `cd apps/intel && uv run python scripts/export_openapi.py && uv run pytest -q tests/test_contract.py`
Expected: `wrote …/packages/contracts/openapi.json`, then PASS. Confirm the schema names are clean: `grep -c '"ReportOut"' ../../packages/contracts/openapi.json` prints at least `1` and `grep -c 'Output"' ../../packages/contracts/openapi.json` prints `0`.

- [ ] **Step 5: Commit**

```bash
git add apps/intel/scripts apps/intel/tests/test_contract.py packages/contracts
git commit -m "feat: export OpenAPI contract with drift check

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Milestone M3 — Web app, read-only

### Task 11: Scaffold Next.js, typed intel client, gallery page

**Files:**
- Create: `apps/web/` (via `create-next-app`), `apps/web/src/lib/intel-api.d.ts` (generated), `apps/web/src/lib/intel.ts`, `apps/web/src/lib/types.ts`, `apps/web/src/lib/report.ts`, `apps/web/src/lib/report.test.ts`, `apps/web/vitest.config.mts`, `apps/web/src/components/RunCard.tsx`, `apps/web/src/app/reports/page.tsx`, `apps/web/src/app/report.css`
- Modify: `apps/web/src/app/layout.tsx`, `apps/web/package.json`

**Interfaces:**
- Consumes: `packages/contracts/openapi.json` (Task 10).
- Produces:
  - `intel` (typed `openapi-fetch` client, server-only), `intelUrl(): string`.
  - Types in `@/lib/types`: `Report`, `RunStatus`, `RunSummary`, `Battlecard`, `CardView`, `CellView`, `Rating`, `SourceOut`, `CompanyProfile`, `CompanyFacts`, `ProgressItem`.
  - Helpers in `@/lib/report`: `SourceIndex`, `indexSources(r)`, `vendorOf(s)`, `slug(s)`, `ratingPct(r, lo)`, `ratingText(r)`, `STATUS_LABEL`, `VERDICT_LABEL`.
  - `<RunCard run={RunSummary} />`.
  - `report.css`: the POC report's CSS (class names `bc`, `glance`, `cmp`, `g g-full`, `cite`, `ev ind|ven`, …) reused by all report components.

- [ ] **Step 1: Scaffold**

```bash
cd /Users/ritik/Projects/competitive-intel-agent/competitive-intel-agent/apps
npx create-next-app@latest web --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm --yes
cd web
npm install openapi-fetch zod server-only
npm install -D openapi-typescript vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/dom @testing-library/jest-dom @playwright/test
npx next --version
```

Expected: the last line prints `Next.js v16.x` (or the current stable major).

- [ ] **Step 2: Scripts and Vitest config**

Add to `apps/web/package.json` `"scripts"`:

```json
    "gen:contracts": "openapi-typescript ../../packages/contracts/openapi.json -o src/lib/intel-api.d.ts",
    "test": "vitest run",
    "e2e": "playwright test"
```

Create `apps/web/vitest.config.mts`:

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", setupFiles: ["./vitest.setup.ts"], include: ["src/**/*.test.{ts,tsx}"] },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
});
```

Create `apps/web/vitest.setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

Run: `npm run gen:contracts`
Expected: `src/lib/intel-api.d.ts` created.

- [ ] **Step 3: Write `src/lib/report.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import { ratingPct, ratingText, slug, vendorOf } from "./report";

describe("report helpers", () => {
  it("knows who published a source", () => {
    expect(vendorOf({ origin: "vendor:Netchex" } as never)).toBe("Netchex");
    expect(vendorOf({ origin: "independent" } as never)).toBeNull();
  });
  it("places ratings on a lo..5 axis, normalising /10 scales", () => {
    expect(ratingPct({ rating: 4.5, out_of: 5 } as never, 4)).toBe(50);
    expect(ratingPct({ rating: 9, out_of: 10 } as never, 4)).toBe(50);
    expect(ratingPct(null, 4)).toBe(0);
  });
  it("formats ratings and slugs", () => {
    expect(ratingText({ rating: 9, out_of: 10, review_count: 1320 } as never)).toBe("9/10 · 1,320 reviews");
    expect(slug("Paycor Inc.")).toBe("paycor-inc");
  });
});
```

- [ ] **Step 4: Run to verify failure**

Run: `cd apps/web && npm test`
Expected: FAIL — cannot resolve `./report`.

- [ ] **Step 5: Create the lib files**

`src/lib/types.ts`:

```ts
import type { components } from "./intel-api";

type S = components["schemas"];
export type Report = S["ReportOut"];
export type RunStatus = S["RunStatusOut"];
export type RunSummary = S["RunSummary"];
export type ProgressItem = S["ProgressItem"];
export type Battlecard = S["Battlecard"];
export type CardView = S["CardView"];
export type CellView = S["CellView"];
export type Rating = S["Rating"];
export type SourceOut = S["SourceOut"];
export type CompanyProfile = S["CompanyProfile"];
export type CompanyFacts = S["CompanyFacts"];
```

`src/lib/intel.ts`:

```ts
import "server-only";
import createClient from "openapi-fetch";
import type { paths } from "./intel-api";

/** On Vercel INTEL_URL comes from the Services binding; locally it's the uvicorn server. */
export const intelUrl = () => process.env.INTEL_URL ?? "http://127.0.0.1:8000";

export const intel = createClient<paths>({ baseUrl: intelUrl() });
```

`src/lib/report.ts`:

```ts
import type { Rating, Report, SourceOut } from "./types";

export type SourceIndex = Map<string, SourceOut>;

export const indexSources = (r: Report): SourceIndex => new Map(r.sources.map((s) => [s.id, s]));

export const vendorOf = (s: Pick<SourceOut, "origin">): string | null =>
  s.origin?.startsWith("vendor:") ? s.origin.slice(7) : null;

export const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

/** Position of a rating on a lo..5 axis, in percent (ratings out of 10 are normalised). */
export function ratingPct(r: Pick<Rating, "rating" | "out_of"> | null | undefined, lo: number): number {
  if (!r || lo >= 5) return 0;
  const v = (r.rating / (r.out_of ?? 5)) * 5;
  return Math.max(0, Math.min(100, ((v - lo) / (5 - lo)) * 100));
}

export function ratingText(r: Rating): string {
  const scale = (r.out_of ?? 5) !== 5 ? `/${r.out_of}` : "";
  const count = r.review_count ? ` · ${r.review_count.toLocaleString("en-US")} reviews` : "";
  return `${r.rating}${scale}${count}`;
}

export const STATUS_LABEL = { full: "Full", partial: "Partial", none: "Not offered", unknown: "Unknown" } as const;
export const VERDICT_LABEL = { lead: "▲ We lead", behind: "▼ They lead", even: "= Even", unknown: "? Unclear" } as const;
```

- [ ] **Step 6: Port the POC CSS**

```bash
cd apps/web
git show 94c57fe:intel/templates/report.html \
  | python3 -c "import sys,re; print(re.search(r'<style>(.*?)</style>', sys.stdin.read(), re.S).group(1))" \
  > src/app/report.css
sed -i '' -e 's/\.tab\[aria-selected="true"\]/.tab[aria-current="page"]/' src/app/report.css
grep -c '\.bc-head' src/app/report.css
```

Expected: the `grep` prints `1` or more. Then append to `src/app/report.css`:

```css
/* Web additions */
.tab { text-decoration: none; display: inline-block; }
.site-nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px; font-size: 14px; }
.site-nav a { color: var(--muted); text-decoration: none; } .site-nav a:hover { color: var(--ink); }
.site-nav .brand { color: var(--ink); font-weight: 700; }
.run-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.run-card { display: block; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; color: var(--ink); text-decoration: none; }
.run-card:hover { border-color: var(--ink); }
.run-card .vs { color: var(--muted); font-size: 14px; margin-top: 4px; }
```

- [ ] **Step 7: Layout, RunCard and gallery page**

Replace `src/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import "./report.css";

export const metadata: Metadata = {
  title: "Battlecards",
  description: "Cited competitive battlecards, researched live by an AI agent with source-quality rules.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="wrap">
          <nav className="site-nav">
            <Link href="/" className="brand">Battlecards</Link>
            <Link href="/reports">All reports</Link>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
```

`src/components/RunCard.tsx`:

```tsx
import Link from "next/link";
import type { RunSummary } from "@/lib/types";

export function RunCard({ run }: { run: RunSummary }) {
  return (
    <Link href={`/reports/${run.id}`} className="run-card">
      <div className="eyebrow">{run.category || "Market"} · {run.run_date}</div>
      <b>{run.company}</b>
      <div className="vs">vs {run.competitors.join(", ")}</div>
    </Link>
  );
}
```

`src/app/reports/page.tsx`:

```tsx
import { RunCard } from "@/components/RunCard";
import { intel } from "@/lib/intel";

export const dynamic = "force-dynamic";

export default async function ReportsPage() {
  const { data: runs } = await intel.GET("/v1/runs", { params: { query: { limit: 50 } }, cache: "no-store" });
  return (
    <main>
      <h1>All reports</h1>
      <p className="meta">Every research run anyone has started. Each one is a permanent, shareable link.</p>
      <div className="run-cards" style={{ marginTop: 20 }}>
        {(runs ?? []).map((r) => <RunCard key={r.id} run={r} />)}
        {!runs?.length && <p className="empty">No reports yet.</p>}
      </div>
    </main>
  );
}
```

- [ ] **Step 8: Run unit tests, type-check, lint**

Run: `cd apps/web && npm test && npx tsc --noEmit && npm run lint`
Expected: 3 tests PASS; no type or lint errors.

- [ ] **Step 9: Check the gallery against the real API**

```bash
cd apps/intel && DATA_DIR=/tmp/intel-smoke uv run uvicorn intel.api:app --port 8000 &
cd apps/web && npm run dev &
sleep 8 && curl -s localhost:3000/reports | grep -o "Netchex" | head -1
kill %1 %2
```

Expected: prints `Netchex`.

- [ ] **Step 10: Commit**

```bash
git add -A apps/web
git commit -m "feat(web): scaffold Next.js app, typed intel client, reports gallery

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Report page shell, Overview tab and shared primitives

**Files:**
- Create: `apps/web/src/components/report/Primitives.tsx`, `apps/web/src/components/report/Overview.tsx`, `apps/web/src/components/report/Appendix.tsx`, `apps/web/src/components/report/ClientBits.tsx`, `apps/web/src/app/reports/[id]/page.tsx`, `apps/web/src/app/reports/[id]/not-found.tsx`
- Test: `apps/web/src/components/report/Primitives.test.tsx`

**Interfaces:**
- Consumes: Task 11 types/helpers, `report.css` classes.
- Produces:
  - `Primitives.tsx`: `<Cite ids index />`, `<EvidenceBadge ids index />`, `<Glyph cell />`, `<GlyphKey />`.
  - `Overview.tsx`: `<Overview report index />`.
  - `Appendix.tsx`: `<Appendix report index />` (changes, positioning, snapshots, sources).
  - `ClientBits.tsx` (client): `<TooltipLayer />`, `<PrintButton />`.
  - Page renders tabs `?tab=overview` (default) and `?tab=<slug(competitor)>`; Task 13 adds the battlecard panel.

- [ ] **Step 1: Write `Primitives.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SourceIndex } from "@/lib/report";
import { Cite, EvidenceBadge, Glyph } from "./Primitives";

const index: SourceIndex = new Map([
  ["S1", { id: "S1", company: "Rival", category: "reviews", url: "https://g2.com/x", title: "G2", origin: "independent" }],
  ["S2", { id: "S2", company: "Acme", category: "pricing", url: "https://acme.com/p", title: "Pricing", origin: "vendor:Acme" }],
] as never);

describe("primitives", () => {
  it("renders citations as footnote numbers and marks vendor sources", () => {
    render(<Cite ids={["S1", "S2", "S99"]} index={index} />);
    expect(screen.getByText("1")).toHaveAttribute("href", "#S1");
    expect(screen.getByText("2")).toHaveClass("v");
    expect(screen.queryByText("99")).toBeNull();
  });
  it("labels evidence as independent when any source is independent", () => {
    render(<EvidenceBadge ids={["S2", "S1"]} index={index} />);
    expect(screen.getByText("Independent")).toBeInTheDocument();
  });
  it("labels vendor-only evidence with the vendor's name", () => {
    render(<EvidenceBadge ids={["S2"]} index={index} />);
    expect(screen.getByText("Acme-stated")).toBeInTheDocument();
  });
  it("marks self-reported matrix cells", () => {
    render(<Glyph cell={{ company: "Acme", status: "full", note: "", sources: ["S2"], self: true } as never} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Full, self-reported");
    expect(screen.getByText("*")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/web && npm test`
Expected: FAIL — cannot resolve `./Primitives`.

- [ ] **Step 3: Create `Primitives.tsx`**

```tsx
import type { CellView } from "@/lib/types";
import { STATUS_LABEL, type SourceIndex, vendorOf } from "@/lib/report";

type Ids = string[] | string | null | undefined;
const list = (ids: Ids, index: SourceIndex) =>
  (typeof ids === "string" ? [ids] : ids ?? []).filter((i) => index.has(i));

export function Cite({ ids, index }: { ids: Ids; index: SourceIndex }) {
  const found = list(ids, index);
  if (!found.length) return null;
  return (
    <sup className="cite">
      {found.map((id, n) => {
        const s = index.get(id)!;
        const v = vendorOf(s);
        return (
          <span key={id}>
            {n > 0 && ","}
            <a href={`#${id}`} className={v ? "v" : undefined}
               title={`${s.title || s.url} · ${v ? `published by ${v}` : "independent"}`}>
              {id.replace(/^S/, "")}
            </a>
          </span>
        );
      })}
    </sup>
  );
}

export function EvidenceBadge({ ids, index }: { ids: Ids; index: SourceIndex }) {
  const srcs = list(ids, index).map((i) => index.get(i)!);
  if (!srcs.length) return null;
  if (srcs.some((s) => !vendorOf(s)))
    return <span className="ev ind" data-tip="Backed by an independent source">Independent</span>;
  const vendor = vendorOf(srcs[0]);
  return <span className="ev ven" data-tip={`Only ${vendor}'s own site says this`}>{vendor}-stated</span>;
}

export function Glyph({ cell }: { cell: CellView }) {
  const label = STATUS_LABEL[cell.status ?? "unknown"];
  const tip = `${cell.company}: ${label}${cell.note ? ` - ${cell.note}` : ""}${
    cell.self ? ` (self-reported: only ${cell.company}'s own site says so)` : ""}`;
  return (
    <>
      <span className={`g g-${cell.status ?? "unknown"}`} role="img"
            aria-label={`${label}${cell.self ? ", self-reported" : ""}`} data-tip={tip} />
      {cell.self && <span className="self" aria-hidden="true">*</span>}
    </>
  );
}

export function GlyphKey() {
  return (
    <div className="glyph-key">
      <span><span className="g g-full" /> Full</span>
      <span><span className="g g-partial" /> Partial / add-on</span>
      <span><span className="g g-none" /> Not offered</span>
      <span><span className="g g-unknown" /> No evidence</span>
      <span><span className="self">*</span> Self-reported (vendor&apos;s own site only)</span>
    </div>
  );
}
```

- [ ] **Step 4: Create `ClientBits.tsx`**

```tsx
"use client";
import { useEffect } from "react";

/** One floating tooltip for every [data-tip] element; citation clicks open the Sources list. */
export function TooltipLayer() {
  useEffect(() => {
    const tip = document.getElementById("tip");
    if (!tip) return;
    const over = (e: MouseEvent) => {
      const el = (e.target as Element).closest<HTMLElement>("[data-tip]");
      if (!el) return tip.classList.remove("on");
      tip.textContent = el.dataset.tip ?? "";
      const b = el.getBoundingClientRect();
      tip.style.left = `${Math.min(window.innerWidth - 290, Math.max(8, b.left + b.width / 2 - 60))}px`;
      tip.style.top = `${b.top - 34 < 4 ? b.bottom + 8 : b.top - 34}px`;
      tip.classList.add("on");
    };
    const click = (e: MouseEvent) => {
      if ((e.target as Element).closest(".cite a")) (document.getElementById("sources") as HTMLDetailsElement | null)?.setAttribute("open", "");
    };
    document.addEventListener("mouseover", over);
    document.addEventListener("click", click);
    return () => { document.removeEventListener("mouseover", over); document.removeEventListener("click", click); };
  }, []);
  return <div id="tip" role="tooltip" />;
}

export function PrintButton() {
  return <button className="btn" onClick={() => window.print()}>Print / PDF</button>;
}
```

- [ ] **Step 5: Create `Overview.tsx`**

```tsx
import type { Report } from "@/lib/types";
import { ratingText, type SourceIndex } from "@/lib/report";
import { Cite, Glyph, GlyphKey } from "./Primitives";

export function Overview({ report, index }: { report: Report; index: SourceIndex }) {
  const v = report.views;
  return (
    <section className="ov">
      <div className="facts">
        {v.names.map((name) => {
          const f = report.facts?.[name] ?? {};
          const domain = report.profiles[name]?.domain;
          const any = f.founded || f.headquarters || f.employees || f.owner;
          return (
            <div className="box fact" key={name}>
              <h3>{name}{name === report.company && <span className="us-tag">US</span>}</h3>
              <dl>
                {domain && <><dt>Website</dt><dd>{domain}</dd></>}
                {f.founded && <><dt>Founded</dt><dd>{f.founded}</dd></>}
                {f.headquarters && <><dt>HQ</dt><dd>{f.headquarters}</dd></>}
                {f.employees && <><dt>Employees</dt><dd>{f.employees}</dd></>}
                {f.owner && <><dt>Owner</dt><dd>{f.owner}</dd></>}
                {!any && <><dt>Facts</dt><dd className="empty">No Wikipedia entry</dd></>}
              </dl>
              {f.wikipedia && <div className="a" style={{ marginTop: 8 }}><a href={f.wikipedia} target="_blank" rel="noopener">Wikipedia ↗</a></div>}
            </div>
          );
        })}
      </div>

      {v.matrix.length > 0 && (
        <div className="box">
          <div className="label">Capability comparison <span className="hint">· hover a dot for details</span></div>
          <div className="grid-wrap"><table className="grid"><tbody>
            <tr><th className="first">Capability</th>{v.names.map((n) => <th key={n} className={n === report.company ? "is-us" : undefined}>{n}</th>)}</tr>
            {v.matrix.map((cap) => (
              <tr key={cap.name}><td className="first">{cap.name}</td>
                {cap.cells.map((c) => <td key={c.company}><Glyph cell={c} /><Cite ids={c.sources} index={index} /></td>)}</tr>
            ))}
          </tbody></table></div>
          <GlyphKey />
        </div>
      )}

      {v.sites.length > 0 && (
        <div className="box">
          <div className="label">Review-site ratings <span className="hint">· independent review sites only</span></div>
          <div className="grid-wrap"><table className="grid"><tbody>
            <tr><th className="first">Company</th>{v.sites.map((s) => <th key={s}>{s}</th>)}</tr>
            {v.market_ratings.map((row) => (
              <tr key={row.name} className={row.name === report.company ? "is-us" : undefined}>
                <td className="first">{row.name}</td>
                {v.sites.map((s) => {
                  const x = row.by_site[s];
                  return (
                    <td key={s}>{x ? (<>
                      <div className="rcell" data-tip={`${row.name} on ${s}: ${ratingText(x)}`}>
                        <b>{x.rating}{(x.out_of ?? 5) !== 5 && <span className="of">/{x.out_of}</span>}</b>
                        <div className="rbar"><span style={{ width: `${Math.round((x.rating / (x.out_of ?? 5)) * 100)}%` }} /></div>
                        {x.review_count ? <small>{x.review_count.toLocaleString("en-US")} reviews</small> : null}
                      </div><Cite ids={x.source} index={index} /></>) : <span className="empty">–</span>}</td>
                  );
                })}
              </tr>
            ))}
          </tbody></table></div>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 6: Create `Appendix.tsx`**

```tsx
import type { Report } from "@/lib/types";
import { type SourceIndex, vendorOf } from "@/lib/report";
import { Cite } from "./Primitives";

const PROFILE_LISTS = [
  ["Reviewers like", "review_strengths"], ["Reviewers complain about", "review_weaknesses"],
  ["Recent changes", "recent_changes"], ["Hiring signals", "hiring_signals"],
] as const;

export function Appendix({ report, index }: { report: Report; index: SourceIndex }) {
  const pos = report.positioning;
  return (
    <div className="appendix">
      <h2>For product marketing</h2>
      {report.changes && (
        <details className="sec" open={report.changes.changes.length > 0}>
          <summary>What changed since last run <span className="sub">vs {report.previous_run} · {report.changes.changes.length} changes</span></summary>
          <div className="sec-body">
            {report.changes.changes.map((ch, i) => (
              <div className="change" key={i}><span className={`tag ${ch.severity}`}>{ch.severity}</span><b>{ch.company}:</b> {ch.change}<Cite ids={ch.sources} index={index} />
                <div className="a">Why it matters: {ch.why_it_matters}</div></div>
            ))}
            {!report.changes.changes.length && <div className="empty">No meaningful changes detected.</div>}
          </div>
        </details>
      )}
      {pos && (
        <details className="sec">
          <summary>Positioning landscape <span className="sub">table stakes, white space, recommended angle</span></summary>
          <div className="sec-body">
            {pos.recommended_angle && (<><h4>Recommended angle for {report.company}</h4>
              <p style={{ margin: 0 }}>{pos.recommended_angle.text}<Cite ids={pos.recommended_angle.sources} index={index} /></p></>)}
            <div className="grid2" style={{ marginTop: 8 }}>
              <div><h4>Table stakes · everyone claims this</h4>
                <table className="plain"><tbody>{pos.table_stakes?.map((t) => (
                  <tr key={t.theme}><td>{t.theme}<Cite ids={t.sources} index={index} /></td><td>{t.companies.join(", ")}</td></tr>))}</tbody></table></div>
              <div><h4>White space · nobody owns this</h4>
                <ul className="qa">{pos.white_space?.map((x) => (
                  <li key={x.opportunity}><div className="q">{x.opportunity}</div><div className="a">{x.evidence}<Cite ids={x.sources} index={index} /></div></li>))}</ul></div>
            </div>
          </div>
        </details>
      )}
      {Object.entries(report.profiles).map(([name, p]) => (
        <details className="sec" key={name}>
          <summary>{name}{name === report.company && " (us)"} · company snapshot <span className="sub">{p.domain ?? ""}</span></summary>
          <div className="sec-body">
            {p.positioning && <div className="pos">{p.positioning.text}<Cite ids={p.positioning.sources} index={index} /></div>}
            {p.pricing_summary && (<><h4>Pricing</h4><div>{p.pricing_summary.text}<Cite ids={p.pricing_summary.sources} index={index} /></div></>)}
            <div className="grid2">
              {PROFILE_LISTS.map(([label, key]) => (p[key]?.length ?? 0) > 0 && (
                <div key={key}><h4>{label}</h4><ul className="bul">{p[key]!.map((x, i) => <li key={i}>{x.text}<Cite ids={x.sources} index={index} /></li>)}</ul></div>
              ))}
            </div>
          </div>
        </details>
      ))}
      <details className="sec" id="sources">
        <summary>Sources <span className="sub">{report.sources.length} · <span style={{ color: "var(--warn)" }}>orange numbers</span> = published by a vendor</span></summary>
        <div className="sec-body"><ol className="sources">
          {report.sources.map((s) => {
            const v = vendorOf(s);
            return (
              <li id={s.id} key={s.id}><span className="id">{s.id}</span><a href={s.url} target="_blank" rel="noopener">{s.title || s.url}</a>
                <span className="src-meta">{s.company === "_market" ? "Market" : s.company} · {s.category.replace("_", " ")} · {v ? <span style={{ color: "var(--warn)" }}>published by {v}</span> : "independent"}{s.published ? ` · ${s.published.slice(0, 10)}` : ""}</span></li>
            );
          })}
        </ol></div>
      </details>
    </div>
  );
}
```

- [ ] **Step 7: Create the report page and 404**

`src/app/reports/[id]/not-found.tsx`:

```tsx
import Link from "next/link";

export default function NotFound() {
  return (
    <main>
      <h1>Report not found</h1>
      <p className="meta">That link doesn&apos;t match any research run. <Link href="/reports">Browse all reports</Link>.</p>
    </main>
  );
}
```

`src/app/reports/[id]/page.tsx`:

```tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import { Appendix } from "@/components/report/Appendix";
import { TooltipLayer } from "@/components/report/ClientBits";
import { Overview } from "@/components/report/Overview";
import { intel } from "@/lib/intel";
import { indexSources, slug } from "@/lib/report";

type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ tab?: string }> };

export default async function ReportPage({ params, searchParams }: Props) {
  const { id } = await params;
  const { tab = "overview" } = await searchParams;
  if (!/^[0-9a-f]{10}$/.test(id)) notFound();

  const status = await intel.GET("/v1/runs/{run_id}", { params: { path: { run_id: id } }, cache: "no-store" });
  if (!status.data) notFound();
  if (status.data.status !== "succeeded" && status.data.status !== "partial") {
    return <main><h1>Research in progress</h1></main>; // replaced by <RunProgress/> in Task 16
  }

  const { data: report } = await intel.GET("/v1/runs/{run_id}/report", {
    params: { path: { run_id: id } }, cache: "force-cache",
  });
  if (!report) notFound();
  const index = indexSources(report);
  const indie = report.sources.filter((s) => s.origin === "independent").length;
  const card = report.battlecards.find((b) => slug(b.competitor) === tab);

  return (
    <main>
      <header className="page-head">
        <div className="eyebrow">Sales battlecards{report.category && ` · ${report.category}`}</div>
        <h1>{report.company} vs {report.competitors.join(", ")}</h1>
        <div className="meta">Updated <b>{report.run_date}</b> · {report.sources.length} sources, <b>{indie}</b> independent · every point links to its source
          {report.degraded && " · researched with fallback search"} · <a href={`/api/runs/${id}/export`}>Markdown</a></div>
      </header>
      <nav className="tabs">
        <Link className="tab" href="?tab=overview" aria-current={!card ? "page" : undefined}>Overview</Link>
        {report.battlecards.map((b) => (
          <Link key={b.competitor} className="tab" href={`?tab=${slug(b.competitor)}`} aria-current={card === b ? "page" : undefined}>vs {b.competitor}</Link>
        ))}
      </nav>
      {card ? <p>Battlecard for {card.competitor}</p> /* replaced in Task 13 */ : <Overview report={report} index={index} />}
      <Appendix report={report} index={index} />
      <footer>Sources gathered via {report.search_provider}, Wikipedia/Wikidata and Hacker News; analysed by {report.model}.
        Every point must cite a collected source. Customer quotes are checked word-for-word and must come from independent sites;
        claims about a competitor can&apos;t rest on another vendor&apos;s own pages.</footer>
      <TooltipLayer />
    </main>
  );
}
```

- [ ] **Step 8: Test, type-check, lint**

Run: `cd apps/web && npm test && npx tsc --noEmit && npm run lint`
Expected: 7 tests PASS; no errors. If `tsc` reports that a schema field is optional (e.g. `report.positioning?.table_stakes`), add `?.`/`?? []` at that use site rather than changing the Python contract.

- [ ] **Step 9: Look at it**

Run the two servers as in Task 11 Step 9 and open `http://localhost:3000/reports` → click the Netchex card. Expected: header, tabs, the facts boxes, the capability grid and ratings table; the collapsed appendix with sources.

- [ ] **Step 10: Commit**

```bash
git add -A apps/web
git commit -m "feat(web): report page with overview, citations, evidence badges and appendix

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Battlecard tab (glance charts, comparison, points)

**Files:**
- Create: `apps/web/src/components/report/Glance.tsx`, `apps/web/src/components/report/Battlecard.tsx`
- Modify: `apps/web/src/app/reports/[id]/page.tsx` (render `<BattlecardView>`)
- Test: `apps/web/src/components/report/Battlecard.test.tsx`

**Interfaces:**
- Consumes: Task 12 primitives; `Report`, `CardView`, `Battlecard`.
- Produces: `<Glance report card view />` (Scorecard, RatingsDotPlot, EvidenceMeter); `<BattlecardView report card view index />`.

- [ ] **Step 1: Write `Battlecard.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BattlecardView } from "./Battlecard";

const report = { company: "Acme", run_date: "2026-10-05", notes: {} } as never;
const view = {
  rows: [], tally: { lead: 5, even: 3, behind: 0, unknown: 0 }, known: 8,
  ratings: [{ site: "G2", us: { site: "G2", rating: 4.6, out_of: 5, review_count: 358, source: "S1" }, them: null }],
  axis_lo: 4, evidence: { total: 16, independent: 6, pct: 38 },
} as never;
const card = {
  competitor: "Rival", overview: "Rival sells to enterprises.", tldr: "We win on speed.", quick_dismiss: "Say this.",
  where_we_win: [{ headline: "Fast setup", detail: "Live in a day.", sources: [] }],
  where_we_lose: [{ headline: "Brand", detail: "", counter: "Ask for references.", sources: [] }],
  landmines: [], objections: [], proof_quotes: [], pricing_comparison: null,
} as never;

describe("BattlecardView", () => {
  it("shows the scorecard, ratings and evidence share", () => {
    render(<BattlecardView report={report} card={card} view={view} index={new Map()} />);
    expect(screen.getByText(/of 8 we lead/)).toBeInTheDocument();
    expect(screen.getByText("38%")).toBeInTheDocument();
    expect(screen.getByText("4.6")).toBeInTheDocument();
    expect(screen.getByText("Fast setup")).toBeInTheDocument();
    expect(screen.getByText(/Ask for references/)).toBeInTheDocument();
  });
  it("renders a battlecard with empty sections", () => {
    const empty = { ...view, ratings: [], known: 0, tally: { lead: 0, even: 0, behind: 0, unknown: 0 }, evidence: { total: 0, independent: 0, pct: 0 } } as never;
    render(<BattlecardView report={report} card={{ ...card, where_we_win: [], where_we_lose: [] } as never} view={empty} index={new Map()} />);
    expect(screen.getByText(/Not enough evidence to compare capabilities/)).toBeInTheDocument();
    expect(screen.getByText(/No independent ratings found/)).toBeInTheDocument();
    expect(screen.getAllByText(/Not enough evidence yet/)).toHaveLength(2);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/web && npm test`
Expected: FAIL — cannot resolve `./Battlecard`.

- [ ] **Step 3: Create `Glance.tsx`**

```tsx
import type { CardView, Rating } from "@/lib/types";
import { ratingPct, ratingText } from "@/lib/report";

function RatingValue({ r }: { r: Rating }) {
  return <>{r.rating}{(r.out_of ?? 5) !== 5 && <span className="of">/{r.out_of}</span>}</>;
}

export function Glance({ us, them, view }: { us: string; them: string; view: CardView }) {
  const { tally, known, ratings, axis_lo: lo, evidence } = view;
  return (
    <div className="glance">
      <div>
        <div className="label">Capability scorecard</div>
        {known ? (<>
          <div className="big">{tally.lead}<small>of {known} we lead</small></div>
          <div className="stack" role="img" aria-label={`We lead ${tally.lead}, even ${tally.even}, they lead ${tally.behind}`}>
            {tally.lead > 0 && <span className="s-lead" style={{ flex: tally.lead }} data-tip={`We lead on ${tally.lead}`} />}
            {tally.even > 0 && <span className="s-even" style={{ flex: tally.even }} data-tip={`Even on ${tally.even}`} />}
            {tally.behind > 0 && <span className="s-behind" style={{ flex: tally.behind }} data-tip={`They lead on ${tally.behind}`} />}
          </div>
          <div className="keys">
            <span><span className="sw s-lead" />We lead <b>{tally.lead}</b></span>
            <span><span className="sw s-even" />Even <b>{tally.even}</b></span>
            <span><span className="sw s-behind" />They lead <b>{tally.behind}</b></span>
          </div>
        </>) : <div className="empty">Not enough evidence to compare capabilities.</div>}
      </div>
      <div>
        <div className="label">Review ratings</div>
        {ratings.length ? (<>
          <div className="legend"><span><span className="sw dot-us" />{us}</span><span><span className="sw dot-them" />{them}</span></div>
          <div className="rplot">
            {ratings.map((x) => {
              const pu = ratingPct(x.us, lo), pt = ratingPct(x.them, lo);
              const close = !!x.us && !!x.them && Math.abs(pu - pt) < 14;
              return (
                <div key={x.site} style={{ display: "contents" }}>
                  <div className="rsite">{x.site}</div>
                  <div className="rtrack">
                    {x.them && (<><span className="rdot them" style={{ left: `${pt}%` }} data-tip={`${them} on ${x.site}: ${ratingText(x.them)}`} />
                      <span className={`rval${close ? " below" : ""}`} style={{ left: `${pt}%` }}><RatingValue r={x.them} /></span></>)}
                    {x.us && (<><span className="rdot us" style={{ left: `${pu}%` }} data-tip={`${us} on ${x.site}: ${ratingText(x.us)}`} />
                      <span className="rval" style={{ left: `${pu}%` }}><RatingValue r={x.us} /></span></>)}
                  </div>
                </div>
              );
            })}
            <div className="raxis"><span>{lo}</span><span>5</span></div>
          </div>
        </>) : <div className="empty">No independent ratings found.</div>}
      </div>
      <div>
        <div className="label">Evidence quality</div>
        <div className="big">{evidence.pct}%<small>independent</small></div>
        <div className="meter" role="img" aria-label={`${evidence.pct} percent of citations independent`}><span style={{ width: `${evidence.pct}%` }} /></div>
        <div className="keys"><span>{evidence.independent} of {evidence.total} sources are reviews, forums, news or analysts - not vendor sites.</span></div>
      </div>
    </div>
  );
}
```

Note: `{evidence.pct}%` renders as two text nodes inside `.big`; the test's `getByText("38%")` matches because Testing Library normalises the element's text content. If it does not, change the JSX to `{`${evidence.pct}%`}`.

- [ ] **Step 4: Create `Battlecard.tsx`**

```tsx
import type { Battlecard, CardView, Report } from "@/lib/types";
import { type SourceIndex, VERDICT_LABEL } from "@/lib/report";
import { PrintButton } from "./ClientBits";
import { Glance } from "./Glance";
import { Cite, EvidenceBadge, Glyph, GlyphKey } from "./Primitives";

type Props = { report: Report; card: Battlecard; view: CardView; index: SourceIndex };

export function BattlecardView({ report, card, view, index }: Props) {
  const us = report.company, them = card.competitor;
  const note = report.notes?.[them];
  return (
    <article className="bc">
      <div className="bc-head">
        <div><h2>{us} <span>vs</span> {them}</h2>{card.overview && <div className="overview">{card.overview}</div>}</div>
        <div className="bc-tools"><span className="updated">Updated {report.run_date}</span><PrintButton /></div>
      </div>

      <Glance us={us} them={them} view={view} />

      <div className="lead">
        <div><div className="label">Bottom line</div><div className="bottom-line">{card.tldr}</div></div>
        <div className="say">
          {card.quick_dismiss
            ? (<><div className="label">Quick dismiss <span className="hint">· say this when they come up</span></div><p>“{card.quick_dismiss}”</p></>)
            : card.pricing_comparison && (<><div className="label">Pricing</div><p>{card.pricing_comparison.text}<Cite ids={card.pricing_comparison.sources} index={index} /></p></>)}
        </div>
      </div>

      {view.rows.length > 0 && (
        <div className="matrix">
          <div className="label">Feature comparison</div>
          <table className="cmp"><tbody>
            <tr><th>Capability</th><th className="us">{us}</th><th className="them">{them}</th><th /></tr>
            {view.rows.map((row) => (
              <tr key={row.name}>
                <td className="cap">{row.name}</td>
                <td className="st"><Glyph cell={row.us} />{row.us.note && <span className="cnote">{row.us.note}</span>}<Cite ids={row.us.sources} index={index} /></td>
                <td className="st"><Glyph cell={row.them} />{row.them.note && <span className="cnote">{row.them.note}</span>}<Cite ids={row.them.sources} index={index} /></td>
                <td className={`verdict v-${row.verdict}`}>{VERDICT_LABEL[row.verdict]}</td>
              </tr>
            ))}
          </tbody></table>
          <GlyphKey />
        </div>
      )}

      <div className="row">
        <div className="cell win">
          <div className="label">✓ Why we win</div>
          <ul className="points">
            {card.where_we_win?.length ? card.where_we_win.map((x, i) => (
              <li key={i}><div className="hl">{x.headline}<EvidenceBadge ids={x.sources} index={index} />{!x.detail && <Cite ids={x.sources} index={index} />}</div>
                {x.detail && <div className="detail">{x.detail}<Cite ids={x.sources} index={index} /></div>}</li>
            )) : <li className="empty">Not enough evidence yet.</li>}
          </ul>
        </div>
        <div className="cell lose">
          <div className="label">⚠ Where they&apos;re strong <span className="hint">· and how to counter</span></div>
          <ul className="points">
            {card.where_we_lose?.length ? card.where_we_lose.map((x, i) => (
              <li key={i}><div className="hl">{x.headline}<EvidenceBadge ids={x.sources} index={index} />{!x.detail && <Cite ids={x.sources} index={index} />}</div>
                {x.detail && <div className="detail">{x.detail}<Cite ids={x.sources} index={index} /></div>}
                {x.counter && <div className="counter"><b>Counter:</b> {x.counter}</div>}</li>
            )) : <li className="empty">Not enough evidence yet.</li>}
          </ul>
        </div>
      </div>

      {(card.landmines?.length || card.objections?.length) ? (
        <div className="row">
          <div className="cell">
            <div className="label">Landmines <span className="hint">· questions to ask the prospect</span></div>
            <ul className="qa">{card.landmines?.length ? card.landmines.map((x, i) => (
              <li key={i}><div className="q">“{x.question}”</div><div className="a">{x.why}<EvidenceBadge ids={x.sources} index={index} /><Cite ids={x.sources} index={index} /></div></li>
            )) : <li className="empty">None backed by independent evidence.</li>}</ul>
          </div>
          <div className="cell">
            <div className="label">Objections <span className="hint">· they say → you say</span></div>
            <ul className="qa">{card.objections?.length ? card.objections.map((x, i) => (
              <li key={i}><div className="they">“{x.objection}”</div><div className="we"><b>→</b> {x.response}<Cite ids={x.sources} index={index} /></div></li>
            )) : <li className="empty">None documented.</li>}</ul>
          </div>
        </div>
      ) : null}

      {((card.quick_dismiss && card.pricing_comparison) || card.proof_quotes?.length) ? (
        <div className="row">
          <div className="cell">
            <div className="label">Pricing</div>
            {card.quick_dismiss && card.pricing_comparison
              ? <div>{card.pricing_comparison.text}<Cite ids={card.pricing_comparison.sources} index={index} /></div>
              : <div className="empty">See bottom line.</div>}
          </div>
          <div className="cell">
            <div className="label">Proof <span className="hint">· real customers, independent sites</span></div>
            {card.proof_quotes?.length ? card.proof_quotes.map((q, i) => <div className="quote" key={i}>“{q.quote}”<Cite ids={q.source} index={index} /></div>)
              : <div className="empty">No independent quotes this run.</div>}
          </div>
        </div>
      ) : null}

      {note && <div className="note"><div className="label">Analyst take</div><p style={{ whiteSpace: "pre-wrap" }}>{note}</p></div>}
    </article>
  );
}
```

Append to `src/app/report.css` (the comparison note class the POC renamed to avoid a clash):

```css
.cmp .cnote { color: var(--muted); font-size: 13px; margin-left: 6px; white-space: normal; }
@media (max-width: 760px) { .cmp .cnote { display: none; } }
```

- [ ] **Step 5: Render it on the page**

In `src/app/reports/[id]/page.tsx` add `import { BattlecardView } from "@/components/report/Battlecard";` and replace the placeholder line with:

```tsx
      {card
        ? <BattlecardView report={report} card={card} view={report.views.cards[report.battlecards.indexOf(card)]} index={index} />
        : <Overview report={report} index={index} />}
```

- [ ] **Step 6: Test, type-check, lint**

Run: `cd apps/web && npm test && npx tsc --noEmit && npm run lint`
Expected: all PASS.

- [ ] **Step 7: Visual check with screenshots**

```bash
cd apps/intel && DATA_DIR=/tmp/intel-smoke uv run uvicorn intel.api:app --port 8000 &
cd apps/web && npm run dev &
sleep 10
ID=$(curl -s "localhost:8000/v1/runs?featured=true" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1280,1400 --screenshot=/tmp/bc.png "http://localhost:3000/reports/$ID?tab=paylocity"
kill %1 %2
```

Expected: `/tmp/bc.png` shows the battlecard with scorecard, rating dots, evidence meter, feature comparison (no strike-through lines on notes), win/lose columns. Compare against the POC screenshot layout; fix any CSS class mismatches.

- [ ] **Step 8: Commit**

```bash
git add -A apps/web
git commit -m "feat(web): battlecard tab with scorecard, ratings plot, evidence meter and comparison

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Markdown export route and Playwright smoke test

**Files:**
- Create: `apps/web/src/app/api/runs/[id]/export/route.ts`, `apps/web/playwright.config.ts`, `apps/web/e2e/global-setup.ts`, `apps/web/e2e/report.spec.ts`
- Modify: `.gitignore` (Playwright output)

**Interfaces:**
- Consumes: `/v1/runs/{id}/export.md`, the seed CLI (Task 8).
- Produces: `GET /api/runs/[id]/export` (text/markdown download); `npm run e2e`.

- [ ] **Step 1: Export route**

`src/app/api/runs/[id]/export/route.ts`:

```ts
import { intelUrl } from "@/lib/intel";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f]{10}$/.test(id)) return new Response("Not found", { status: 404 });
  const res = await fetch(`${intelUrl()}/v1/runs/${id}/export.md`, { cache: "no-store" });
  if (!res.ok) return new Response("Not found", { status: res.status === 409 ? 409 : 404 });
  return new Response(await res.text(), {
    headers: { "content-type": "text/markdown; charset=utf-8", "content-disposition": `attachment; filename="battlecards-${id}.md"` },
  });
}
```

- [ ] **Step 2: Playwright config and seeding**

`apps/web/playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test";
import path from "node:path";

const DATA_DIR = path.resolve(__dirname, ".e2e-data");

export default defineConfig({
  testDir: "e2e",
  globalSetup: "./e2e/global-setup.ts",
  use: { baseURL: "http://localhost:3100" },
  webServer: [
    {
      command: "uv run uvicorn intel.api:app --port 8100",
      cwd: path.resolve(__dirname, "../intel"),
      url: "http://127.0.0.1:8100/health",
      env: { DATA_DIR, RUN_MODE: "inline" },
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 3100",
      url: "http://localhost:3100",
      env: { INTEL_URL: "http://127.0.0.1:8100" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
```

`apps/web/e2e/global-setup.ts`:

```ts
import { execSync } from "node:child_process";
import { rmSync } from "node:fs";
import path from "node:path";

export default function globalSetup() {
  const dataDir = path.resolve(__dirname, "../.e2e-data");
  rmSync(dataDir, { recursive: true, force: true });
  execSync("uv run python -m intel.seed tests/fixtures/netchex_snapshot.json", {
    cwd: path.resolve(__dirname, "../../intel"),
    env: { ...process.env, DATA_DIR: dataDir },
    stdio: "inherit",
  });
}
```

Note: `globalSetup` runs after the web servers start. The intel API reads the store per request, so seeding after start-up is fine.

`apps/web/e2e/report.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("a seeded report renders its overview and battlecards", async ({ page }) => {
  await page.goto("/reports");
  await page.getByText("Netchex").first().click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Netchex vs Paylocity");
  await expect(page.getByText("Capability comparison")).toBeVisible();

  await page.getByRole("link", { name: "vs Paylocity" }).click();
  await expect(page).toHaveURL(/tab=paylocity/);
  await expect(page.getByText("Capability scorecard")).toBeVisible();
  await expect(page.getByText("Evidence quality")).toBeVisible();
  expect(await page.locator("sup.cite a").count()).toBeGreaterThan(5);

  const res = await page.request.get(page.url().replace(/\?.*/, "").replace("/reports/", "/api/runs/") + "/export");
  expect(res.ok()).toBeTruthy();
  expect(await res.text()).toContain("# Competitive intelligence: Netchex");
});

test("unknown report ids show the not-found page", async ({ page }) => {
  await page.goto("/reports/0000000000");
  await expect(page.getByText("Report not found")).toBeVisible();
});
```

Append to `.gitignore`:

```
apps/web/.e2e-data/
apps/web/test-results/
apps/web/playwright-report/
```

- [ ] **Step 3: Run**

Run: `cd apps/web && npx playwright install chromium && npm run e2e`
Expected: 2 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add -A apps/web .gitignore
git commit -m "feat(web): markdown export and Playwright smoke test

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Milestone M4 — Live runs

### Task 15: Run form, input schema and `/api/runs` route handlers

**Files:**
- Create: `apps/web/src/lib/run-schema.ts`, `apps/web/src/lib/run-schema.test.ts`, `apps/web/src/app/api/runs/route.ts`, `apps/web/src/app/api/runs/[id]/route.ts`, `apps/web/src/components/RunForm.tsx`
- Modify: `apps/web/src/app/page.tsx` (landing page)

**Interfaces:**
- Consumes: intel `POST /v1/runs`, `GET /v1/runs/{id}`, `GET /v1/runs?featured=true`.
- Produces:
  - `RunInput` (zod) and `type RunInputT`; `toIntelBody(v: RunInputT)`.
  - `POST /api/runs` → `202 {run_id, status, reused}` | `400 {error}` | `429 {error}` | `503 {error}`.
  - `GET /api/runs/[id]` → `RunStatus` JSON (no-store) | `404 {error}`.
  - `<RunForm />` (client).

- [ ] **Step 1: Write `src/lib/run-schema.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import { RunInput, toIntelBody } from "./run-schema";

const ok = { company: { name: " Acme ", domain: "" }, competitors: [{ name: "Rival", domain: "rival.io" }], category: "help desk" };

describe("RunInput", () => {
  it("accepts a normal request and drops empty domains", () => {
    const v = RunInput.parse(ok);
    expect(toIntelBody(v)).toEqual({ company: { name: "Acme" }, competitors: [{ name: "Rival", domain: "rival.io" }], category: "help desk" });
  });
  it.each([
    [{ ...ok, competitors: [] }, "Add at least one competitor"],
    [{ ...ok, competitors: Array.from({ length: 5 }, (_, i) => ({ name: `C${i}` })) }, "Up to 4 competitors"],
    [{ ...ok, competitors: [{ name: "acme" }] }, "must all be different"],
    [{ ...ok, company: { name: "  " } }, "Company name is required"],
  ])("rejects bad input %#", (input, message) => {
    const r = RunInput.safeParse(input);
    expect(r.success).toBe(false);
    expect(r.error!.issues[0].message).toContain(message);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/web && npm test`
Expected: FAIL — cannot resolve `./run-schema`.

- [ ] **Step 3: Create `src/lib/run-schema.ts`**

```ts
import { z } from "zod";

const Company = z.object({
  name: z.string().trim().min(1, "Company name is required").max(60, "Names must be 60 characters or fewer"),
  domain: z.string().trim().max(100).optional(),
});

export const RunInput = z
  .object({
    company: Company,
    competitors: z.array(Company).min(1, "Add at least one competitor").max(4, "Up to 4 competitors"),
    category: z.string().trim().max(80).optional().default(""),
  })
  .refine(
    (v) => new Set([v.company, ...v.competitors].map((c) => c.name.toLowerCase())).size === v.competitors.length + 1,
    { message: "Company and competitor names must all be different" },
  );

export type RunInputT = z.infer<typeof RunInput>;

const clean = (c: { name: string; domain?: string }) => (c.domain ? { name: c.name, domain: c.domain } : { name: c.name });

export const toIntelBody = (v: RunInputT) => ({
  company: clean(v.company),
  competitors: v.competitors.map(clean),
  category: v.category,
});
```

- [ ] **Step 4: Route handlers**

`src/app/api/runs/route.ts`:

```ts
import { NextResponse } from "next/server";
import { intel } from "@/lib/intel";
import { RunInput, toIntelBody } from "@/lib/run-schema";

const detail = (e: unknown): string => {
  const d = (e as { detail?: unknown })?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg).replace(/^Value error, /, "");
  return "Something went wrong starting the research run.";
};

export async function POST(req: Request) {
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Body must be JSON" }, { status: 400 }); }
  const parsed = RunInput.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message ?? "Invalid input" }, { status: 400 });

  const { data, error, response } = await intel.POST("/v1/runs", { body: toIntelBody(parsed.data) });
  if (error || !data) {
    const status = response.status === 422 ? 400 : response.status;
    return NextResponse.json({ error: detail(error) }, { status });
  }
  return NextResponse.json(data, { status: 202 });
}
```

`src/app/api/runs/[id]/route.ts`:

```ts
import { NextResponse } from "next/server";
import { intel } from "@/lib/intel";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f]{10}$/.test(id)) return NextResponse.json({ error: "Not found" }, { status: 404 });
  const { data } = await intel.GET("/v1/runs/{run_id}", { params: { path: { run_id: id } }, cache: "no-store" });
  if (!data) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json(data, { headers: { "cache-control": "no-store" } });
}
```

- [ ] **Step 5: `RunForm` and landing page**

`src/components/RunForm.tsx`:

```tsx
"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

type Row = { name: string; domain: string };
const blank: Row = { name: "", domain: "" };

export function RunForm() {
  const router = useRouter();
  const [company, setCompany] = useState<Row>({ name: "Netchex", domain: "netchex.com" });
  const [rivals, setRivals] = useState<Row[]>([
    { name: "Paylocity", domain: "paylocity.com" }, { name: "isolved", domain: "isolvedhcm.com" }, { name: "Paycor", domain: "paycor.com" },
  ]);
  const [category, setCategory] = useState("HCM software");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    const res = await fetch("/api/runs", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ company, competitors: rivals.filter((r) => r.name.trim()), category }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok) router.push(`/reports/${data.run_id}`);
    else { setError(data.error ?? "Something went wrong."); setBusy(false); }
  }

  const field = (row: Row, set: (r: Row) => void, label: string) => (
    <div className="form-row">
      <input aria-label={`${label} name`} placeholder="Company name" value={row.name} onChange={(e) => set({ ...row, name: e.target.value })} />
      <input aria-label={`${label} domain`} placeholder="domain.com (optional)" value={row.domain} onChange={(e) => set({ ...row, domain: e.target.value })} />
    </div>
  );

  return (
    <form className="box run-form" onSubmit={submit}>
      <div className="label">Your company</div>
      {field(company, setCompany, "Your company")}
      <div className="label" style={{ marginTop: 14 }}>Competitors <span className="hint">· up to 4</span></div>
      {rivals.map((r, i) => (
        <div key={i}>{field(r, (v) => setRivals(rivals.map((x, j) => (j === i ? v : x))), `Competitor ${i + 1}`)}</div>
      ))}
      {rivals.length < 4 && <button type="button" className="btn" onClick={() => setRivals([...rivals, blank])}>+ Add competitor</button>}
      <div className="label" style={{ marginTop: 14 }}>Category <span className="hint">· helps disambiguate names</span></div>
      <input aria-label="Category" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="e.g. help desk software" />
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="btn primary" type="submit" disabled={busy}>{busy ? "Starting…" : "Research this market"}</button>
      <p className="hint" style={{ marginTop: 8 }}>Takes about 3-5 minutes. Uses free AI models and search, so a run may occasionally need a retry.</p>
    </form>
  );
}
```

Append to `src/app/report.css`:

```css
.run-form input { width: 100%; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--ink); font: inherit; }
.form-row { display: grid; grid-template-columns: 1.2fr 1fr; gap: 8px; margin-bottom: 8px; }
.btn.primary { background: var(--ink); color: var(--bg); border-color: var(--ink); padding: 10px 18px; font-weight: 600; margin-top: 14px; display: block; }
.btn:disabled { opacity: .6; cursor: progress; }
.form-error { color: var(--lose); font-size: 14px; }
.hero { display: grid; grid-template-columns: 1.1fr 1fr; gap: 28px; align-items: start; margin-bottom: 40px; }
.hero p { color: var(--muted); font-size: 17px; }
.hero ul { list-style: disc; padding-left: 20px; color: var(--muted); }
@media (max-width: 860px) { .hero { grid-template-columns: 1fr; } }
```

Replace `src/app/page.tsx`:

```tsx
import { RunCard } from "@/components/RunCard";
import { RunForm } from "@/components/RunForm";
import { intel } from "@/lib/intel";

export const dynamic = "force-dynamic";

export default async function Home() {
  const { data: featured } = await intel.GET("/v1/runs", { params: { query: { featured: true, limit: 6 } }, cache: "no-store" });
  return (
    <main>
      <section className="hero">
        <div>
          <div className="eyebrow">AI competitive intelligence</div>
          <h1>Sales battlecards an agent researches live - with every claim cited.</h1>
          <p>Name a company and its competitors. The agent searches review sites, forums, news and the vendors&apos; own pages, then writes one-screen battlecards for sales reps.</p>
          <ul>
            <li>Every point links to its source; uncited claims are deleted in code.</li>
            <li>Customer quotes are checked word-for-word and must come from independent sites.</li>
            <li>A vendor&apos;s own blog can&apos;t be the only evidence against a rival.</li>
          </ul>
        </div>
        <RunForm />
      </section>
      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Featured reports</h2>
      <div className="run-cards">
        {(featured ?? []).map((r) => <RunCard key={r.id} run={r} />)}
        {!featured?.length && <p className="empty">No featured reports yet.</p>}
      </div>
    </main>
  );
}
```

- [ ] **Step 6: Test, type-check, lint**

Run: `cd apps/web && npm test && npx tsc --noEmit && npm run lint`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add -A apps/web
git commit -m "feat(web): landing page with run form, validated /api/runs handlers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Live progress page

**Files:**
- Create: `apps/web/src/components/RunProgress.tsx`, `apps/web/src/components/RunProgress.test.tsx`
- Modify: `apps/web/src/app/reports/[id]/page.tsx` (use `<RunProgress>`)

**Interfaces:**
- Consumes: `GET /api/runs/[id]` (Task 15), `RunStatus` type.
- Produces: `<RunProgress runId initial />` — polls every 3s; on `succeeded`/`partial` calls `router.refresh()`; on `failed` shows `error` and a link home.

- [ ] **Step 1: Write `RunProgress.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RunProgress } from "./RunProgress";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const base = { id: "0123456789", created_at: "", company: "Acme", competitors: ["Rival"], degraded: false, current_stage: null };

describe("RunProgress", () => {
  it("shows each stage's state and notes", () => {
    render(<RunProgress runId="0123456789" initial={{ ...base, status: "running", progress: [
      { stage: "collect", status: "done", at: "", note: "45 sources, 20 independent" },
      { stage: "profiles", status: "running", at: "", note: "" },
    ] } as never} />);
    expect(screen.getByText("Collecting sources")).toBeInTheDocument();
    expect(screen.getByText("45 sources, 20 independent")).toBeInTheDocument();
    expect(screen.getByText("Profiling companies").closest("li")).toHaveClass("running");
  });
  it("explains a failed run instead of spinning forever", () => {
    render(<RunProgress runId="0123456789" initial={{ ...base, status: "failed", error: "The profiles step failed: model down", progress: [] } as never} />);
    expect(screen.getByRole("alert")).toHaveTextContent("model down");
    expect(screen.getByRole("link", { name: /try again/i })).toHaveAttribute("href", "/");
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/web && npm test`
Expected: FAIL — cannot resolve `./RunProgress`.

- [ ] **Step 3: Create `RunProgress.tsx`**

```tsx
"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { RunStatus } from "@/lib/types";

const STAGES: [string, string][] = [
  ["collect", "Collecting sources"], ["profiles", "Profiling companies"], ["battlecards", "Writing battlecards"],
  ["matrix", "Building the capability matrix"], ["positioning", "Analysing positioning"], ["finalize", "Finishing up"],
];
const ICON: Record<string, string> = { done: "✓", running: "…", retrying: "↻", skipped: "–", failed: "✕", waiting: "·" };

export function RunProgress({ runId, initial }: { runId: string; initial: RunStatus }) {
  const router = useRouter();
  const [status, setStatus] = useState(initial);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (status.status === "succeeded" || status.status === "partial") { router.refresh(); return; }
    if (status.status === "failed") return;
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`/api/runs/${runId}`, { cache: "no-store" });
        if (res.ok) setStatus(await res.json());
      } finally { setTick((n) => n + 1); }
    }, 3000);
    return () => clearTimeout(t);
  }, [status, tick, runId, router]);

  const byStage = new Map(status.progress.map((p) => [p.stage, p]));
  return (
    <main>
      <div className="eyebrow">Research run · {runId}</div>
      <h1>{status.company} vs {status.competitors.join(", ")}</h1>
      <p className="meta">{status.status === "failed" ? "This run stopped." : "The agent is researching. This page updates by itself - usually 3-5 minutes."}</p>
      <ul className="box progress">
        {STAGES.map(([key, label]) => {
          const p = byStage.get(key);
          const state = p?.status ?? "waiting";
          return (
            <li key={key} className={state}>
              <span className="pi" aria-hidden="true">{ICON[state]}</span>
              <span><b>{label}</b>{p?.note && <span className="pn">{p.note}</span>}</span>
            </li>
          );
        })}
      </ul>
      {status.degraded && <p className="hint">Today&apos;s search budget is used up, so this run uses fallback search with fewer review sources.</p>}
      {status.status === "failed" && (
        <div className="box" role="alert" style={{ marginTop: 14 }}>
          <b>Couldn&apos;t finish this report.</b> {status.error}
          <div style={{ marginTop: 8 }}><Link href="/">Try again</Link> - free AI models are sometimes busy.</div>
        </div>
      )}
    </main>
  );
}
```

Append to `src/app/report.css`:

```css
.progress { list-style: none; padding: 8px 22px; }
.progress li { display: flex; gap: 12px; padding: 10px 0; border-top: 1px solid var(--line); color: var(--faint); }
.progress li:first-child { border-top: 0; }
.progress li.done, .progress li.running, .progress li.retrying { color: var(--ink); }
.progress li.failed { color: var(--lose); }
.progress .pi { width: 18px; text-align: center; font-weight: 700; }
.progress li.done .pi { color: var(--win); }
.progress li.running .pi { animation: pulse 1.2s ease-in-out infinite; }
.progress .pn { display: block; color: var(--muted); font-size: 13px; }
@keyframes pulse { 50% { opacity: .3; } }
@media (prefers-reduced-motion: reduce) { .progress li.running .pi { animation: none; } }
```

- [ ] **Step 4: Use it on the report page**

In `src/app/reports/[id]/page.tsx` add `import { RunProgress } from "@/components/RunProgress";` and replace the placeholder return with:

```tsx
    return <RunProgress runId={id} initial={status.data} />;
```

- [ ] **Step 5: Test, type-check, lint**

Run: `cd apps/web && npm test && npx tsc --noEmit && npm run lint`
Expected: all PASS.

- [ ] **Step 6: Live end-to-end check with real keys (manual, ~5 minutes)**

```bash
cd apps/intel && uv run uvicorn intel.api:app --port 8000 &
cd apps/web && npm run dev &
```

Open `http://localhost:3000`, submit the prefilled form. Expected: redirect to `/reports/<id>`, the checklist advances through all six stages, then the page refreshes into the full report. Stop both servers.

- [ ] **Step 7: Commit**

```bash
git add -A apps/web
git commit -m "feat(web): live run progress with failure explanation

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 17: One-command local dev, CI workflow and README

**Files:**
- Create: `scripts/dev.sh`, `.github/workflows/ci.yml`
- Delete: `.github/workflows/weekly.yml`
- Modify: `README.md`, `.env.example`

**Interfaces:**
- Produces: `./scripts/dev.sh` (seeds, starts intel on :8000 and web on :3000); CI on push/PR.

- [ ] **Step 1: `scripts/dev.sh`**

```bash
#!/usr/bin/env bash
# Local dev: seed the featured report, run the intel API and the web app together.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/apps/intel"
uv sync -q
uv run python -m intel.seed tests/fixtures/netchex_snapshot.json >/dev/null
uv run uvicorn intel.api:app --port 8000 --reload &
INTEL_PID=$!
trap 'kill $INTEL_PID 2>/dev/null' EXIT
cd "$ROOT/apps/web"
[ -d node_modules ] || npm install
INTEL_URL=http://127.0.0.1:8000 npm run dev
```

Run: `chmod +x scripts/dev.sh`

- [ ] **Step 2: `.github/workflows/ci.yml`**

```yaml
name: CI
on:
  push:
  pull_request:

jobs:
  intel:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: apps/intel } }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run pytest -q

  web:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: apps/web } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 24, cache: npm, cache-dependency-path: apps/web/package-lock.json }
      - run: npm ci
      - name: Contract types are up to date
        run: npm run gen:contracts && git diff --exit-code src/lib/intel-api.d.ts
      - run: npm run lint
      - run: npx tsc --noEmit
      - run: npm test

  e2e:
    runs-on: ubuntu-latest
    needs: [intel, web]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - uses: actions/setup-node@v4
        with: { node-version: 24, cache: npm, cache-dependency-path: apps/web/package-lock.json }
      - run: cd apps/intel && uv sync
      - run: cd apps/web && npm ci && npx playwright install --with-deps chromium
      - run: cd apps/web && npm run e2e
```

Run: `git rm -q .github/workflows/weekly.yml`

- [ ] **Step 3: Add the new settings to `.env.example`**

Append:

```
# ── Web app guardrails (fully open demo on free tiers) ───────
# New research runs allowed per day (identical same-day requests reuse a run for free)
RUNS_PER_DAY=30
# Tavily calls per day before falling back to DuckDuckGo (free tier ≈ 1,000/month)
TAVILY_CALLS_PER_DAY=30
# inline = background thread (local dev) · queue = Vercel Queues (deployed)
RUN_MODE=inline
```

- [ ] **Step 4: Rewrite `README.md`**

Replace the "Setup", "Command reference", "Weekly runs" and "Project layout" sections with:

````markdown
## Architecture

```
Browser ──▶ web  (Next.js App Router, TypeScript)         public
              │  private service binding (INTEL_URL)
              ▼
            intel (FastAPI, Python)                         private
              │  ◀── Vercel Queue "run-stages": collect → profiles → battlecards
              │                                  → matrix → positioning → finalize
              ▼
            Vercel Blob: runs/{id}.json · cache/… · usage/{day}.json
```

- **Python owns the rules.** Citations, vendor-vs-independent evidence, verbatim quotes,
  rating checks, the capability matrix and evidence scoring live in `apps/intel/intel/domain`.
  The web app only draws what the API returns.
- **One contract.** Pydantic → `packages/contracts/openapi.json` → generated TypeScript types.
  CI fails if they drift.
- **Fits free tiers.** Each research stage finishes well under Vercel Hobby's 300s limit and is
  safe to retry; identical same-day requests reuse a run; search results are cached and shared.

## Run it locally

```bash
cp .env.example .env               # add OPENROUTER_API_KEY (free) and TAVILY_API_KEY (free tier)
./scripts/dev.sh                   # http://localhost:3000 (API on :8000)
```

Requires [uv](https://docs.astral.sh/uv/) and Node.js 24.

## Tests

```bash
cd apps/intel && uv run pytest -q          # domain rules, stages, API (offline fakes)
cd apps/web && npm test && npm run e2e     # components + Playwright smoke test
```

## Project layout

```
apps/intel/intel/domain/   evidence, ratings, verification, scoring (pure)
apps/intel/intel/stages.py the six research stages      runner.py  retries, resume
apps/intel/intel/api.py    FastAPI /v1                   seed.py    featured runs
apps/web/src/app/          landing, reports gallery, report page, /api/runs
apps/web/src/components/   report components (charts are plain SVG/HTML)
packages/contracts/        openapi.json
```

The original CLI still works: `cd apps/intel && uv run python run.py`.
````

- [ ] **Step 5: Verify the dev script**

Run: `./scripts/dev.sh` then in another terminal `curl -s localhost:3000 | grep -o "Featured reports"`.
Expected: prints `Featured reports`. Stop with Ctrl-C.

- [ ] **Step 6: Commit**

```bash
git add -A scripts .github README.md .env.example
git commit -m "chore: one-command local dev, CI workflow, README architecture

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Milestone M5 — Ship on Vercel

### Task 18: Vercel Blob store

**Files:**
- Modify: `apps/intel/intel/store.py`, `apps/intel/pyproject.toml`
- Test: `apps/intel/tests/test_store.py` (add a `BlobStore` test with a fake client)

**Interfaces:**
- Produces: `BlobStore(client=None)` implementing `Store`; `make_store()` returns it when `BLOB_READ_WRITE_TOKEN` is set.

- [ ] **Step 1: Add the SDK**

Run: `cd apps/intel && uv add "vercel>=0.3"` and then confirm the API surface:
`uv run python -c "from vercel.blob import AsyncBlobClient, list_objects; import inspect; print(inspect.iscoroutinefunction(list_objects))"`
Record whether it prints `True` or `False`; the implementation below handles both.

- [ ] **Step 2: Write the test**

Append to `tests/test_store.py`:

```python
from types import SimpleNamespace

from intel.store import BlobStore


class FakeBlobClient:
    def __init__(self):
        self.objects = {}

    async def put(self, pathname, body, access, overwrite):
        self.objects[pathname] = body

    async def get(self, pathname, access):
        if pathname not in self.objects:
            return None

        async def stream():
            yield self.objects[pathname]

        return SimpleNamespace(status_code=200, stream=stream())


def test_blob_store_round_trip(monkeypatch):
    client = FakeBlobClient()
    monkeypatch.setattr("intel.store._list_blobs",
                        lambda prefix: [k for k in client.objects if k.startswith(prefix)])
    s = BlobStore(client=client)
    s.put_json("runs/a.json", {"x": 1})
    assert s.get_json("runs/a.json") == {"x": 1}
    assert s.get_json("runs/missing.json") is None
    assert s.list_keys("runs/") == ["runs/a.json"]
```

- [ ] **Step 3: Run to verify failure**

Run: `cd apps/intel && uv run pytest -q tests/test_store.py`
Expected: FAIL with `ImportError: cannot import name 'BlobStore'`

- [ ] **Step 4: Implement `BlobStore`**

Add to `intel/store.py` (and `import asyncio`, `import inspect` at the top):

```python
def _list_blobs(prefix: str) -> list[str]:
    from vercel.blob import list_objects

    async def go():
        keys, cursor = [], None
        while True:
            kwargs = {"prefix": prefix, "limit": 1000}
            if cursor:
                kwargs["cursor"] = cursor
            page = list_objects(**kwargs)
            if inspect.isawaitable(page):
                page = await page
            keys += [b.pathname for b in page.blobs]
            cursor = getattr(page, "cursor", None)
            if not getattr(page, "has_more", False) or not cursor:
                return keys

    return asyncio.run(go())


class BlobStore:
    """Vercel Blob (private). Sync wrapper over the async SDK; call from worker threads only."""

    def __init__(self, client=None):
        if client is None:
            from vercel.blob import AsyncBlobClient

            client = AsyncBlobClient()
        self.client = client

    def get_json(self, key: str) -> Any | None:
        async def go():
            res = await self.client.get(key, access="private")
            if res is None or res.status_code != 200:
                return None
            return b"".join([chunk async for chunk in res.stream])

        raw = asyncio.run(go())
        return json.loads(raw) if raw else None

    def put_json(self, key: str, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False).encode()
        asyncio.run(self.client.put(key, body, access="private", overwrite=True))

    def list_keys(self, prefix: str) -> list[str]:
        return _list_blobs(prefix)
```

Change `make_store`:

```python
def make_store() -> Store:
    if os.getenv("BLOB_READ_WRITE_TOKEN"):
        return BlobStore()
    return LocalStore(data_dir())
```

- [ ] **Step 5: Run tests and commit**

Run: `cd apps/intel && uv run pytest -q && uv run ruff check .`
Expected: all PASS.

```bash
git add -A apps/intel
git commit -m "feat: Vercel Blob store selected by BLOB_READ_WRITE_TOKEN

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 19: Queue dispatcher, stage subscriber and `vercel.json`

**Files:**
- Create: `apps/intel/intel/worker.py`, `vercel.json`
- Modify: `apps/intel/intel/dispatch.py`, `apps/intel/pyproject.toml`
- Test: `apps/intel/tests/test_worker.py`

**Interfaces:**
- Consumes: `runner.run_stage` (Task 7), `vercel.queue` (`Topic`, `Message`, `subscribe`, `send`).
- Produces: topic `run-stages` with payload `{"run_id": str, "stage": str}`; `worker.handle_stage(message)`; `QueueDispatcher.start(run_id)` sends `{"run_id", "stage": "collect"}`; `make_dispatcher` returns it when `settings.run_mode == "queue"`.

- [ ] **Step 1: Write `tests/test_worker.py`**

```python
import asyncio
from types import SimpleNamespace

from intel import worker


def test_handle_stage_runs_one_stage_and_queues_the_next(monkeypatch):
    calls, sent = [], []
    monkeypatch.setattr(worker, "run_stage",
                        lambda store, settings, run_id, stage, attempt: calls.append((run_id, stage, attempt)) or "profiles")

    async def fake_send(topic, payload, idempotency_key=None):
        sent.append((payload, idempotency_key))

    monkeypatch.setattr(worker, "send", fake_send)
    monkeypatch.setattr(worker, "_store", lambda: "store")
    monkeypatch.setattr(worker, "_settings", lambda: "settings")
    msg = SimpleNamespace(payload={"run_id": "0123456789", "stage": "collect"},
                          metadata=SimpleNamespace(delivery_count=2))
    asyncio.run(worker.handle_stage(msg))
    assert calls == [("0123456789", "collect", 2)]
    assert sent == [({"run_id": "0123456789", "stage": "profiles"}, "0123456789:profiles")]


def test_last_stage_queues_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr(worker, "run_stage", lambda *a, **k: None)
    monkeypatch.setattr(worker, "send", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(worker, "_store", lambda: None)
    monkeypatch.setattr(worker, "_settings", lambda: None)
    msg = SimpleNamespace(payload={"run_id": "0123456789", "stage": "finalize"}, metadata=SimpleNamespace(delivery_count=1))
    asyncio.run(worker.handle_stage(msg))
    assert sent == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/intel && uv run pytest -q tests/test_worker.py`
Expected: FAIL with `ImportError: cannot import name 'worker'`

- [ ] **Step 3: Create `intel/worker.py`**

```python
"""Vercel Queues subscriber: runs one research stage per message, then queues the next.

Registered in pyproject.toml under [[tool.vercel.subscribers]]; Vercel compiles it into a
private queue-triggered function. Delivery is at-least-once - run_stage is idempotent."""
from __future__ import annotations

import asyncio
from functools import cache

from vercel.queue import Message, Topic, send, subscribe

from .config import load_settings
from .runner import MAX_ATTEMPTS, run_stage
from .store import make_store

stages_topic = Topic[dict[str, str]]("run-stages")


@cache
def _store():
    return make_store()


@cache
def _settings():
    return load_settings()


@subscribe(topic=stages_topic, max_attempts=MAX_ATTEMPTS, retry_after=20)
async def handle_stage(message: Message[dict[str, str]]) -> None:
    run_id, stage = message.payload["run_id"], message.payload["stage"]
    nxt = await asyncio.to_thread(run_stage, _store(), _settings(), run_id, stage,
                                  attempt=message.metadata.delivery_count)
    if nxt:
        await send(stages_topic, {"run_id": run_id, "stage": nxt}, idempotency_key=f"{run_id}:{nxt}")
```

- [ ] **Step 4: Queue dispatcher**

Add to `intel/dispatch.py`:

```python
class QueueDispatcher:
    """Production: hand the first stage to Vercel Queues; the subscriber chains the rest."""

    def start(self, run_id: str) -> None:
        from vercel.queue.sync import QueueClient

        QueueClient().send("run-stages", {"run_id": run_id, "stage": "collect"}, idempotency_key=f"{run_id}:collect")
```

and change `make_dispatcher`:

```python
def make_dispatcher(settings: Config, store: Store) -> Dispatcher:
    if settings.run_mode == "queue":
        return QueueDispatcher()
    return InlineDispatcher(store, settings)
```

Append to `apps/intel/pyproject.toml`:

```toml
[[tool.vercel.subscribers]]
entrypoint = "intel.worker"
```

- [ ] **Step 5: Create `vercel.json` at the repo root**

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "services": {
    "web": {
      "root": "apps/web",
      "bindings": [{ "type": "service", "service": "intel", "format": "url", "env": "INTEL_URL" }]
    },
    "intel": {
      "root": "apps/intel",
      "entrypoint": "intel.api:app"
    }
  },
  "rewrites": [{ "source": "/(.*)", "destination": { "service": "web" } }]
}
```

`intel` has no top-level rewrite, so it is private: only reachable through the `web` binding.

- [ ] **Step 6: Run tests and commit**

Run: `cd apps/intel && uv run pytest -q && uv run ruff check .`
Expected: all PASS.

```bash
git add -A apps/intel vercel.json
git commit -m "feat: Vercel Queues stage subscriber, queue dispatcher and Services config

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 20: Deploy (with the owner) and seed production

**Files:**
- Modify: `README.md` (deploy section)

**Interfaces:**
- Consumes: everything above. Requires the owner's Vercel account — the executor pauses for the owner at Step 1.

- [ ] **Step 1: Owner logs in and links the project**

Ask the owner to run in the repo root: `! npx vercel@latest login` then `! npx vercel@latest link`.

- [ ] **Step 2: Create a private Blob store and set environment variables**

```bash
npx vercel@latest blob store add battlecards-store --access private
npx vercel@latest env add RUN_MODE production        # value: queue
npx vercel@latest env add LLM_PROVIDER production    # value: openrouter
npx vercel@latest env add OPENROUTER_API_KEY production
npx vercel@latest env add TAVILY_API_KEY production
npx vercel@latest env add RUNS_PER_DAY production    # value: 30
npx vercel@latest env add TAVILY_CALLS_PER_DAY production  # value: 30
```

Confirm `BLOB_READ_WRITE_TOKEN` was added automatically: `npx vercel@latest env ls production | grep BLOB`.

- [ ] **Step 3: Deploy a preview and seed it**

```bash
npx vercel@latest deploy
npx vercel@latest env pull apps/intel/.env.production.local --environment=production
cd apps/intel && set -a && . ./.env.production.local && set +a && uv run python -m intel.seed tests/fixtures/netchex_snapshot.json
```

Expected: the deploy prints a preview URL; the seed prints a run id. Open the preview URL: the featured Netchex report appears; start one live run and watch it complete.

- [ ] **Step 4: Add the rate-limit rule (owner, dashboard)**

In the Vercel dashboard → Firewall → add a rate-limit rule: path `/api/runs`, method `POST`, 5 requests per 10 minutes per IP, action `Deny`.

- [ ] **Step 5: Promote to production, document, commit**

Run: `npx vercel@latest deploy --prod`

Add to `README.md`:

````markdown
## Deploy (Vercel Hobby, free)

```bash
npx vercel link
npx vercel blob store add battlecards-store --access private
npx vercel env add RUN_MODE production            # queue
npx vercel env add OPENROUTER_API_KEY production
npx vercel env add TAVILY_API_KEY production
npx vercel deploy --prod
```

Then seed featured reports with `uv run python -m intel.seed <snapshot.json>` using the pulled
production env, and add a Firewall rate-limit rule on `POST /api/runs`.
````

```bash
rm -f apps/intel/.env.production.local
git add README.md
git commit -m "docs: deployment guide

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
