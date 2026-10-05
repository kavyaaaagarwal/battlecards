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
