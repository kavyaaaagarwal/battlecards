import pytest
from pydantic import ValidationError

from intel.runs import (
    Budget,
    CapacityError,
    RunRequest,
    create_run,
    mark,
    new_run_doc,
    run_id_for,
    run_key,
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
