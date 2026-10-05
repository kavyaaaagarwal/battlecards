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


class RecordingDispatcher:
    def __init__(self):
        self.started = []

    def start(self, run_id):
        self.started.append(run_id)


def test_stalled_run_is_redispatched_on_resubmit(store, offline, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    settings = load_settings("/nonexistent")
    dispatcher = RecordingDispatcher()
    client = TestClient(create_app(store=store, settings=settings, deps=FAKE_DEPS, dispatcher=dispatcher))
    run_id = client.post("/v1/runs", json=BODY).json()["run_id"]
    assert dispatcher.started == [run_id]
    # a fresh in-flight run is not started twice
    client.post("/v1/runs", json=BODY)
    assert dispatcher.started == [run_id]
    # the worker died: no progress for over 10 minutes -> resubmitting restarts it
    doc = store.get_json(f"runs/{run_id}.json")
    doc.update(status="running", created_at="2000-01-01T00:00:00+00:00",
               progress=[{"stage": "collect", "status": "running", "at": "2000-01-01T00:00:00+00:00", "note": ""}])
    store.put_json(f"runs/{run_id}.json", doc)
    assert client.post("/v1/runs", json=BODY).json()["reused"] is True
    assert dispatcher.started == [run_id, run_id]
