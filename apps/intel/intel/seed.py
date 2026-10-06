"""Import POC snapshot.json files as finished runs, so the demo has content on day one.

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


def import_snapshot(store: Store, snapshot: dict) -> str:
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
    doc.update(status="succeeded", stages_done=list(STAGES), created_at=f"{day}T00:00:00+00:00")
    for stage in STAGES:
        mark(doc, stage, "done", "Imported from an earlier run")
    doc["views"] = build_views(doc)
    store.put_json(run_key(run_id), doc)
    return run_id


def main() -> None:
    ap = argparse.ArgumentParser(description="Import snapshot.json files as finished runs.")
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args()
    store = make_store()
    for p in args.paths:
        print(import_snapshot(store, json.loads(p.read_text())))


if __name__ == "__main__":
    main()
