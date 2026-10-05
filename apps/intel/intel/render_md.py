"""Renders a report as GitHub-friendly Markdown."""
from __future__ import annotations

from .domain.views import build_views


# ── Markdown ────────────────────────────────────────────────
def _cite_md(ids, by_id) -> str:
    if not ids:
        return ""
    ids = [ids] if isinstance(ids, str) else ids
    return " " + " ".join(f"[{i.lstrip('S')}]({by_id[i]['url']})" for i in ids if i in by_id)


def render_markdown(r: dict) -> str:
    by_id = {s["id"]: s for s in r["sources"]}
    c = lambda ids: _cite_md(ids, by_id)  # noqa: E731
    out: list[str] = []
    w = out.append

    w(f"# Competitive intelligence: {r['company']}")
    w(f"*{r['run_date']} · {r['category'] or 'market'} · vs {', '.join(r['competitors'])}*\n")
    w(
        f"> {len(r['sources'])} sources · every claim cited · "
        f"{r['stats']['claims_dropped']} uncited claims and {r['stats']['quotes_dropped']} "
        "unverifiable quotes removed automatically\n"
    )

    views = build_views(r)
    glyph = {"full": "●", "partial": "◐", "none": "○", "unknown": "–"}
    verdict = {"lead": "▲ we lead", "behind": "▼ they lead", "even": "= even", "unknown": "?"}
    for card, cv in zip(r["battlecards"], views["cards"], strict=True):
        w(f"## {r['company']} vs {card['competitor']}")
        if card.get("overview"):
            w(f"*{card['overview']}*\n")
        w(f"**Bottom line:** {card['tldr']}\n")
        if card.get("quick_dismiss"):
            w(f"**Quick dismiss** (say this when they come up):\n> \"{card['quick_dismiss']}\"\n")
        if cv["rows"]:
            w(f"### Feature comparison (we lead {cv['tally']['lead']}, even {cv['tally']['even']}, "
              f"they lead {cv['tally']['behind']})")
            w(f"| Capability | {r['company']} | {card['competitor']} | |\n|---|---|---|---|")
            for row in cv["rows"]:
                cell = lambda x: f"{glyph[x['status']]} {x.get('note') or ''}{c(x.get('sources'))}".strip()  # noqa: E731
                w(f"| {row['name']} | {cell(row['us'])} | {cell(row['them'])} | {verdict[row['verdict']]} |")
            w("\n*● full · ◐ partial / add-on · ○ not offered · – no evidence*\n")
        if cv["ratings"]:
            fmt = lambda x: f"{x['rating']:g}" + (f" ({x['review_count']:,} reviews)" if x.get("review_count") else "") if x else "–"  # noqa: E731
            w("**Ratings:** " + " · ".join(f"{x['site']}: {r['company']} {fmt(x['us'])} vs {fmt(x['them'])}" for x in cv["ratings"]) + "\n")
        w(f"*Evidence: {cv['evidence']['pct']}% of cited sources are independent.*\n")
        w("### ✓ Why we win")
        for x in card["where_we_win"]:
            detail = f" {x['detail']}" if x.get("detail") else ""
            w(f"- **{x.get('headline') or x.get('text')}**{detail}{c(x['sources'])}")
        w("\n### ⚠ Where they're strong (and how to counter)")
        for x in card["where_we_lose"]:
            detail = f" {x['detail']}" if x.get("detail") else ""
            w(f"- **{x.get('headline') or x.get('text')}**{detail}{c(x['sources'])}")
            if x.get("counter"):
                w(f"  - *Counter:* {x['counter']}")
        if card["landmines"]:
            w("\n### Landmines (questions to ask the prospect)")
            for x in card["landmines"]:
                w(f"- **\"{x['question']}\"** — {x['why']}{c(x['sources'])}")
        if card["objections"]:
            w("\n### Objections")
            for x in card["objections"]:
                w(f"- *\"{x['objection']}\"*  \n  → {x['response']}{c(x['sources'])}")
        if card.get("pricing_comparison"):
            p = card["pricing_comparison"]
            w(f"\n### Pricing\n{p['text']}{c(p['sources'])}")
        if card["proof_quotes"]:
            w("\n### Proof")
            for q in card["proof_quotes"]:
                w(f"> \"{q['quote']}\"{c(q['source'])}\n")
        note = r["notes"].get(card["competitor"])
        if note:
            w(f"\n### Analyst take\n{note.strip()}")
        w("\n---\n")

    if r.get("changes") is not None:
        w("## What changed since last run")
        if r.get("previous_run"):
            w(f"*Compared with {r['previous_run']}*\n")
        if not r["changes"]["changes"]:
            w("No meaningful changes detected.\n")
        for ch in r["changes"]["changes"]:
            w(f"- **[{ch['severity'].upper()}] {ch['company']}:** {ch['change']}{c(ch['sources'])}  ")
            w(f"  *Why it matters:* {ch['why_it_matters']}")
        w("")

    pos = r["positioning"]
    w("## Positioning landscape")
    if pos.get("table_stakes"):
        w("### Table stakes (everyone says this)")
        w("| Theme | Claimed by |\n|---|---|")
        for t in pos["table_stakes"]:
            w(f"| {t['theme']}{c(t['sources'])} | {', '.join(t['companies'])} |")
    if pos.get("white_space"):
        w("\n### White space (nobody owns this)")
        for x in pos["white_space"]:
            w(f"- **{x['opportunity']}** {x['evidence']}{c(x['sources'])}")
    if pos.get("recommended_angle"):
        a = pos["recommended_angle"]
        w(f"\n### Recommended angle for {r['company']}\n{a['text']}{c(a['sources'])}")
    if r["notes"].get("_positioning"):
        w(f"\n### Analyst take\n{r['notes']['_positioning'].strip()}")
    w("")

    w("## Company snapshots")
    for name, p in r["profiles"].items():
        w(f"### {name}" + (f" ({p['domain']})" if p.get("domain") else ""))
        if p.get("positioning"):
            w(f"*{p['positioning']['text']}*{c(p['positioning']['sources'])}\n")
        if p.get("pricing_summary"):
            w(f"**Pricing:** {p['pricing_summary']['text']}{c(p['pricing_summary']['sources'])}\n")
        if p.get("pricing_tiers"):
            w("| Tier | Price | Notable |\n|---|---|---|")
            for t in p["pricing_tiers"]:
                w(f"| {t['name']} | {t['price']}{c(t['sources'])} | {t['notable']} |")
            w("")
        for label, key in [
            ("Recent changes", "recent_changes"),
            ("What reviewers like", "review_strengths"),
            ("What reviewers complain about", "review_weaknesses"),
            ("Hiring signals", "hiring_signals"),
        ]:
            if p.get(key):
                w(f"**{label}**")
                for x in p[key]:
                    w(f"- {x['text']}{c(x['sources'])}")
                w("")

    w("## Sources")
    for s in r["sources"]:
        w(f"- **{s['id']}** [{s['title']}]({s['url']}) · {s['company']} · {s['category']}")
    w(
        f"\n---\n*Generated by competitive-intel-agent · model `{r['model']}` · "
        f"search `{r['search_provider']}` · {r['usage']['calls']} LLM calls, "
        f"{r['usage']['input_tokens']:,} in / {r['usage']['output_tokens']:,} out tokens*"
    )
    return "\n".join(out)
