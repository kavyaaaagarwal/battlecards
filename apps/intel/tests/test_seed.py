import json
from pathlib import Path

from intel.runs import run_key
from intel.seed import import_snapshot
from intel.store import MemoryStore

FX = Path(__file__).parent / "fixtures"


def test_import_snapshot_creates_finished_run():
    store = MemoryStore()
    snap = json.loads((FX / "netchex_snapshot.json").read_text())
    run_id = import_snapshot(store, snap)
    doc = store.get_json(run_key(run_id))
    assert doc["status"] == "succeeded"
    assert doc["company"] == "Netchex" and doc["competitors"] == ["Paylocity", "isolved", "Paycor"]
    assert len(doc["battlecards"]) == 3 and doc["views"]["cards"]
    assert doc["stats"]["vendor_quotes_dropped"] == snap["stats"]["vendor_quotes_dropped"]
    assert [p["status"] for p in doc["progress"]] == ["done"] * 6
    assert import_snapshot(store, snap) == run_id  # idempotent
