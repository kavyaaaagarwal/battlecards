# Battlecards - AI competitive intelligence

Name a company and its competitors. An agent researches review sites, forums, news, Wikipedia
and the vendors' own pages, then writes **one-screen sales battlecards** with a capability
comparison, review-rating charts and an evidence-quality score. **Every claim links to the
page it came from**, and the source-quality rules are enforced in code, not just requested
in a prompt.

Works for any market: help desk software, HCM, travel tech, fintech.

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

### Running it for free

| Piece | Free option | Notes |
|---|---|---|
| Web data | **Tavily** free tier: 1,000 credits/month, no card ([tavily.com](https://tavily.com)) | One run with 3 competitors uses about 28 credits (6 searches per company). `TAVILY_CALLS_PER_DAY` (default 150) caps daily use; past it, runs fall back to DuckDuckGo. |
| LLM | **OpenRouter** free models (`LLM_PROVIDER=openrouter`, blank `LLM_MODEL`) | Picks the best free models automatically, with fallbacks. |
| LLM | Gemini / Claude / GPT | Set `LLM_PROVIDER` and the key in `.env`. |

## Tests

```bash
cd apps/intel && uv run pytest -q          # domain rules, stages, API (offline fakes)
cd apps/web && npm test && npm run e2e     # components + Playwright smoke test
```

## What you get

| Section | What it answers |
|---|---|
| **Battlecard per competitor** | TL;DR for reps, where we win, where we lose, landmine questions, objection handling, pricing comparison, customer quotes |
| **Positioning landscape** | What everyone claims (table stakes), what buyers want that nobody owns (white space), a recommended angle |
| **Company snapshots** | Positioning, published pricing tiers, recent launches, what reviewers praise and complain about, hiring signals |
| **What changed** | From the second run onwards: pricing, launches and messaging shifts since the last run, ranked by severity |
| **Analyst take** | Your own commentary, added from `notes/` (see below) |

## How it works

```
names ─▶ 1. COLLECT ──────▶ 2. PROFILES ──▶ 3. BATTLECARDS ──▶ 4. MATRIX ──▶ 5. POSITIONING ──▶ 6. FINALIZE
         vendor pages,       one LLM call     one per            capability    table stakes,      change diff,
         reviews, ratings,   per company,     competitor,        grid, cells   white space        chart data
         forums, news,       verified         verified,          need evidence
         Wikipedia, HN,                       capped to 1 screen
         independent "X vs Y"
```

Each stage is a separate, retryable step that saves its results, so a flaky model call
resumes where it stopped instead of starting over.

- **Company-independent query plan** (`apps/intel/intel/collect.py`). If you don't pin a company's
  domain, it finds the official site automatically. Searches about its own pricing,
  changelog and positioning are limited to that domain. Customer sentiment comes from
  review sites and forums. The prompts keep what a company *says* separate from what
  customers *experience*.
- **Citations are enforced in code, not just requested in the prompt** (`apps/intel/intel/domain/`).
  A claim that cites no real source ID is deleted. A customer quote is checked
  word-for-word against the page it cites, and paraphrases or invented quotes are
  removed. The report shows how many items were removed.
- **Pluggable LLM** (`apps/intel/intel/llm.py`). Works with Anthropic, OpenAI or any
  OpenAI-compatible endpoint (Gemini, Groq, Ollama). Structured output is checked
  against Pydantic schemas, with retries that rotate to fallback models.
- **Pluggable search** (`apps/intel/intel/search.py`). Tavily (best quality, free tier) or
  DuckDuckGo plus direct page fetching (no key needed). Results are cached and shared
  between runs, so re-researching a company within 24h costs no credits.

## Adding your own take

Add markdown files to `apps/intel/notes/`; they appear as an "Analyst take" on the next run:

```
apps/intel/notes/zendesk.md        → on the Zendesk battlecard
apps/intel/notes/positioning.md    → under the positioning landscape
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

The original CLI still works: `cd apps/intel && uv run python run.py` (reads the repo-root `.env`).

## Limitations

- It can only know what is publicly on the web. Pricing that sits behind "contact
  sales" stays unknown.
- Review sites sometimes block scraping. Tavily usually gets through; DuckDuckGo
  mode may return fewer reviews.
- Verification checks that every claim has a source and every quote is real. It does
  not prove the model read the source correctly, so read the cited pages before
  sending a battlecard to sales.
