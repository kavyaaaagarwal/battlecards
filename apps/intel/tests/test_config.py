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


def test_default_daily_search_budget_fits_a_full_run(monkeypatch):
    # one run with 3 competitors makes ~28 search calls; the cap must allow a few fresh runs a day
    monkeypatch.delenv("TAVILY_CALLS_PER_DAY", raising=False)
    assert load_settings("/nonexistent").tavily_calls_per_day >= 150


def test_default_source_text_is_capped_at_4000_chars(monkeypatch):
    monkeypatch.delenv("MAX_CHARS_PER_SOURCE", raising=False)
    assert load_settings("/nonexistent").max_chars_per_source == 4000
