import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Battlecard, CardView } from "@/lib/types";
import { BattlecardView } from "./Battlecard";

const report = { company: "Acme", run_date: "2026-10-05", notes: {} } as never;
const view = {
  rows: [], tally: { lead: 5, even: 3, behind: 0, unknown: 0 }, known: 8,
  ratings: [{ site: "G2", us: { site: "G2", rating: 4.6, out_of: 5, review_count: 358, source: "S1" }, them: null }],
  axis_lo: 4, evidence: { total: 16, independent: 6, pct: 38 },
} as unknown as CardView;
const card = {
  competitor: "Rival", overview: "Rival sells to enterprises.", tldr: "We win on speed.", quick_dismiss: "Say this.",
  where_we_win: [{ headline: "Fast setup", detail: "Live in a day.", sources: [] }],
  where_we_lose: [{ headline: "Brand", detail: "", counter: "Ask for references.", sources: [] }],
  landmines: [], objections: [], proof_quotes: [], pricing_comparison: null,
} as unknown as Battlecard;

describe("BattlecardView", () => {
  it("shows the scorecard, ratings and evidence share", () => {
    render(<BattlecardView report={report} card={card} view={view} index={new Map()} />);
    expect(screen.getByText(/of 8 we lead/)).toBeInTheDocument();
    expect(screen.getByText("38%")).toBeInTheDocument();
    expect(screen.getByText("4.6")).toBeInTheDocument();
    expect(screen.getByText("Fast setup")).toBeInTheDocument();
    expect(screen.getByText(/Ask for references/)).toBeInTheDocument();
  });
  it("renders a battlecard with empty sections", () => {
    const empty = { ...view, ratings: [], known: 0, tally: { lead: 0, even: 0, behind: 0, unknown: 0 }, evidence: { total: 0, independent: 0, pct: 0 } } as CardView;
    render(<BattlecardView report={report} card={{ ...card, where_we_win: [], where_we_lose: [] }} view={empty} index={new Map()} />);
    expect(screen.getByText(/Not enough evidence to compare capabilities/)).toBeInTheDocument();
    expect(screen.getByText(/No independent ratings found/)).toBeInTheDocument();
    expect(screen.getAllByText(/Not enough evidence yet/)).toHaveLength(2);
  });
});
