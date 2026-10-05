"""Characterization tests: the refactor must not change what reps see."""
import json
from pathlib import Path

from intel.domain.views import build_views
from intel.render_md import render_markdown

FX = Path(__file__).parent / "fixtures"


def snapshot() -> dict:
    return json.loads((FX / "netchex_snapshot.json").read_text())


def test_views_match_golden():
    got = json.loads(json.dumps(build_views(snapshot()), sort_keys=True))
    assert got == json.loads((FX / "netchex_views.json").read_text())


def test_markdown_matches_golden():
    assert render_markdown(snapshot()) == (FX / "netchex_report.md").read_text()
