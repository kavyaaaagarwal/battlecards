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
