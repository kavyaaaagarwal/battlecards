"""Private HTTP API for the web app. Not publicly routed on Vercel.

    uv run uvicorn intel.api:app --port 8000
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from .api_models import CreateRunOut, ReportOut, RunStatusOut, RunSummary
from .config import load_settings, settings_problem
from .dispatch import make_dispatcher
from .render_md import render_markdown
from .runs import RUN_ID_PATTERN, CapacityError, RunRequest, create_run, run_key
from .store import StorageNotConfigured, make_store

log = logging.getLogger(__name__)
RunId = Annotated[str, Path(pattern=RUN_ID_PATTERN)]
DONE = ("succeeded", "partial")
STALL_AFTER = timedelta(minutes=10)  # a stage never runs longer than ~4 minutes


def is_stalled(doc: dict) -> bool:
    """An unfinished run whose worker died (e.g. the process restarted) - safe to restart,
    because stages resume instead of repeating finished work."""
    if doc["status"] not in ("queued", "running"):
        return False
    last = max([doc.get("created_at", "")] + [p.get("at", "") for p in doc.get("progress", [])])
    return datetime.now(timezone.utc) - datetime.fromisoformat(last) > STALL_AFTER


def create_app(*, store=None, settings=None, deps=None, dispatcher=None) -> FastAPI:
    app = FastAPI(title="Battlecard intel API", version="1.0.0", separate_input_output_schemas=False)
    ctx = SimpleNamespace(store=store, settings=settings, deps=deps, dispatcher=dispatcher)
    app.state.ctx = ctx

    @app.exception_handler(StorageNotConfigured)
    def storage_missing(_req: Request, exc: StorageNotConfigured) -> JSONResponse:
        log.error("%s", exc)
        return JSONResponse({"detail": str(exc)}, status_code=503)

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
        if not reused or is_stalled(doc):
            get_dispatcher().start(doc["id"])
            doc = load(doc["id"])
        return CreateRunOut(run_id=doc["id"], status=doc["status"], reused=reused)

    @app.get("/v1/runs", response_model=list[RunSummary])
    def list_runs(limit: Annotated[int, Query(ge=1, le=50)] = 20) -> list[RunSummary]:
        docs = [d for k in get_store().list_keys("runs/") if (d := get_store().get_json(k))]
        docs = [d for d in docs if d.get("status") in DONE]
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
