# Battlecard App — Design

**Date:** 2026-10-05
**Status:** Approved in conversation; awaiting written-spec review

## 1. Purpose

Turn the working competitive-intelligence POC (Python CLI → HTML/Markdown files) into a
portfolio-grade web application that the owner can demo to interviewers.

- **Audience:** interviewers and anyone with the link. No accounts.
- **Usage:** fully open. Anyone can browse reports *and* start a live research run.
- **Budget:** $0. Free tiers only, with graceful degradation when they run out.
- **Success:** a public URL that loads fast, never breaks during a demo, shows the agent
  working live, and a repository whose architecture, tests and README stand up to review.

Non-goals (YAGNI): user accounts, teams, billing, a SQL database, per-URL source history,
editable analyst notes in the UI.

## 2. Architecture

One Vercel project using **Services**:

```
Browser ──▶ web  (Next.js App Router, TypeScript, Tailwind)  — public
              │  private service binding (INTEL_URL)
              ▼
            intel (Python 3.12, FastAPI)                      — not publicly routed
              │  ◀── Vercel Queue topic "run-stages" (push mode)
              ▼
            Vercel Blob (JSON files)
```

Decisions:

1. **`intel` is private.** Only `web` reaches it, through a Services binding. All public
   guardrails (validation, rate limits, daily cap) live in `web`'s two route handlers.
2. **`intel` owns the domain rules.** Evidence classification, verification, ratings
   checks, matrix rules and evidence scoring stay in one tested Python package. `web` renders.
3. **One contract.** Pydantic models → FastAPI `openapi.json` → `openapi-typescript` types
   in `packages/contracts`. CI fails if the generated types drift.
4. **The CLI keeps working** (`python -m intel run …`), executing stages inline.

### Platform constraints (verified 2026-10-05 against Vercel docs)

| Need | Hobby plan | Consequence |
|---|---|---|
| Next.js + Python in one project | Services supports both, plus private bindings | ✅ |
| Function duration | **300s max, not configurable** | A run is split into stages, each <300s |
| Background jobs | Queues public beta; Python SDK; 1,000,000 ops/month included | ✅ ~20 ops per run |
| Storage | Vercel Blob free tier | ✅ |

## 3. Repository layout

```
apps/web/                 Next.js app
apps/intel/
  intel/
    domain/               pure rules, no I/O: verify, origins, ratings, matrix, views (scoring)
    stages/               collect · profiles · battlecards · matrix · positioning · finalize
    llm.py search.py collect.py prompts.py models.py config.py
    store.py              Storage interface: LocalStore (disk) | BlobStore (Vercel Blob)
    runner.py             inline runner (CLI/tests) + queue handler
    api.py                FastAPI app
    render_md.py          Markdown export (kept); Jinja HTML removed
  tests/
packages/contracts/       openapi.json + generated TS types
vercel.json               services, rewrites, queue trigger
.github/workflows/ci.yml
```

## 4. Storage: JSON files in Vercel Blob

Vercel functions have no persistent filesystem, so the POC's `reports/` and `.cache/` move
to Blob behind a `Store` interface (`get_json`, `put_json`, `list`, `exists`). Locally,
`LocalStore` writes to `./data/`.

```
runs/{run_id}.json    one document per run (same shape as today's snapshot.json, plus
                      status, progress[], stages_done, degraded, inputs)
cache/{hash}.json     search/page/API cache (DiskCache interface unchanged)
usage/{day}.json      daily counters for the global budget cap
```

- **Run ID** = short hash of (sorted company names + domains, category, UTC date).
  If `runs/{id}.json` exists, the existing run is returned (`reused: true`).
- **Gallery** = `list("runs/")`; featured runs are flagged in the document.
- **Previous run** for "what changed" = latest earlier run with the same company set.
- **Seed:** the POC's existing `reports/*/snapshot.json` are imported as featured runs.
- Stages run strictly in sequence, so one writer touches a run file at a time.

## 5. Run lifecycle

1. `POST /api/runs` (web) validates input with zod (1–4 competitors, names ≤ 60 chars,
   optional domains), checks the daily cap, and calls `intel POST /v1/runs`.
2. `intel` writes `runs/{id}.json` (`status: queued`) and sends `{run_id, stage: "collect"}`
   to the queue, unless the run already exists.
3. The queue consumer (`POST /queues/stage`) loads the run, executes the stage, saves it,
   and sends the next stage.
4. The browser polls `GET /api/runs/{id}` every 3s and shows a stage checklist; when the run
   finishes it refreshes into the full report.

| # | Stage | Work | Required |
|---|---|---|---|
| 1 | collect | domain discovery, search plan, Wikipedia/HN, origin labels | yes |
| 2 | profiles | one LLM call per company (parallel) + verification + ratings check | yes |
| 3 | battlecards | one LLM call per competitor (parallel) + evidence rules + caps | yes |
| 4 | matrix | capability matrix | optional |
| 5 | positioning | positioning landscape | optional |
| 6 | finalize | change diff vs previous run, compute views, mark done | yes |

Rules:

- **Idempotent at item level.** A stage skips companies/competitors already present in the
  run document, so redelivery or retry never repeats LLM or search calls.
- **Time budget.** Each stage gets a ~240s deadline passed to the LLM client; rate-limit waits
  are capped to the remaining time. Running out raises; the queue retries and the stage resumes.
- **Failure.** A required stage failing 3 deliveries → `status: failed` with the reason.
  An optional stage failing → skipped, run ends `partial`.
- **Progress** is `progress: [{stage, status, at, note}]` in the run document (e.g.
  "Tavily budget reached — using DuckDuckGo").
- **Locally / in tests:** `INLINE_STAGES=1` runs all stages in-process with no queue.

## 6. Guardrails for a fully open, $0 demo

- Vercel Firewall rate-limit rule on `POST /api/runs` (per IP).
- Global daily cap on runs and Tavily calls via `usage/{day}.json`; when Tavily's share is
  spent, search falls back to DuckDuckGo and the run is marked `degraded`.
- Same-day identical requests reuse the existing run; search/page cache is shared across runs,
  so researching a company again within 24h costs no search credits.
- LLM defaults to free OpenRouter models (existing auto-pick + fallbacks).

## 7. API contract (`intel`, private, `/v1`)

| Endpoint | Purpose |
|---|---|
| `POST /v1/runs` | `{company:{name,domain?}, competitors:[{name,domain?}], category?}` → `{run_id, status, reused}` |
| `GET /v1/runs/{id}` | status + progress (polled) |
| `GET /v1/runs/{id}/report` | profiles, battlecards, matrix, positioning, changes, sources (no page text), facts, **views** |
| `GET /v1/runs?featured=1&limit=` | gallery summaries |
| `GET /v1/runs/{id}/export.md` | Markdown export |
| `POST /queues/stage` | queue consumer (not public) |

`views` (moved from `render.build_views` into `intel/domain/views.py`) contains, per
battlecard: capability rows with verdicts, lead/even/behind tally, ratings pairs and axis,
evidence counts and %, and per-cell `self_reported` flags; plus overview ratings and matrix.
Scoring therefore has exactly one implementation.

## 8. Web app (Next.js App Router)

```
app/page.tsx               landing: pitch, "Research a market" form (prefilled example), featured reports
app/reports/page.tsx       gallery
app/reports/[id]/page.tsx  Server Component; running → <RunProgress/> (client, polls); done → report
app/api/runs/route.ts      POST: validate → limits → intel
app/api/runs/[id]/route.ts GET: status passthrough
components/report/         Overview (Facts, CapabilityGrid, RatingsTable);
                           Battlecard (Header, Scorecard, RatingsDotPlot, EvidenceMeter, BottomLine,
                           FeatureComparison, WinLose, Landmines, Objections, PricingProof);
                           Citation, EvidenceBadge, Glyph, SourcesList, PmmAppendix
```

- Tabs are URL state (`?tab=<competitor-slug>`) so links can point at one battlecard.
- Charts are plain SVG/HTML components ported from the current template — no chart library;
  validated palette (us = blue `#2a78d6`/`#3987e5`, them = orange `#eb6834`/`#d95926`), light +
  dark, hover tooltips, print-to-PDF layout preserved.
- Finished reports are immutable → cached; running reports are `no-store`.

## 9. Protected behaviour (must survive the refactor, each covered by a test)

1. Claims without a valid citation are dropped.
2. Quotes must be verbatim (fuzzy ≥ 94) and not hosted on a vendor's site.
3. A claim about company X cannot rest only on a rival vendor's site (profiles, threats,
   landmines, matrix cells).
4. Ratings kept only if the number appears on an independent review-site page and ≤ `out_of`;
   unverifiable review counts cleared.
5. Matrix: no-evidence cells → `unknown`; all-unknown rows dropped; vendor-only cells flagged
   self-reported.
6. Origin classification: vendor domain / newswire → vendor; else independent.
7. Evidence % = independent ÷ unique cited sources; scorecard lead/even/behind excludes unknown.
8. Item caps: 3 win, 3 threats, 3 landmines, 3 objections, 2 quotes.
9. LLM robustness: empty/irrelevant replies rejected, model rotation on retry, transient
   provider errors retried, reasoning disabled for OpenRouter.

## 10. Testing

| Layer | Tooling | Scope |
|---|---|---|
| Domain | pytest (offline) | existing 8 tests ported + new tests for §9 items 7–9 |
| Characterization | pytest | the real Netchex snapshot's views and Markdown captured before refactor; must match after |
| Stages | pytest, fake LLM/search, in-memory store | each stage; idempotency (second run makes zero LLM calls); resume after simulated crash |
| API | FastAPI TestClient | `/v1` endpoints, validation, run reuse |
| Contract | CI script | generated TS types match `openapi.json` |
| Web | Vitest + Testing Library | EvidenceBadge, Scorecard, Citation; route handler validation and limits |
| E2E | Playwright (one smoke test) | seeded report renders; tabs switch; charts and citations visible |

CI: one GitHub Actions workflow (ruff, pytest, tsc, eslint, vitest, contract check, Playwright).
The POC's weekly cron workflow is removed.

## 11. Milestones

- **M0 Safety net:** git, move POC into `apps/intel/` unchanged, characterization tests.
- **M1 Python refactor:** `domain/`, `Store`, stages, inline runner; CLI works; all tests green.
- **M2 Service:** FastAPI `/v1`, queue consumer, OpenAPI + contracts.
- **M3 Web, read-only:** report page rendering seeded runs at parity with today's HTML.
- **M4 Web, live runs:** form, progress, guardrails.
- **M5 Ship:** Vercel deploy (Services, Blob, Queue, Firewall rule), seed, README with
  architecture diagram and demo GIF.

## 12. Risks

- **Queues is public beta.** Mitigation: the queue touches only `runner.py`; the inline runner
  is always available, and a client-driven "advance stage" fallback could replace push mode.
- **Free OpenRouter models are flaky / rate-limited.** Mitigation: existing rotation and retries;
  seeded featured reports always work; failures surface clearly.
- **Tavily free quota (1,000/month).** Mitigation: shared cache, run reuse, daily cap, DDG fallback.
