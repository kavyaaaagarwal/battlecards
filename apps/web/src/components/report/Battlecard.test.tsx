import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Battlecard, CardView } from "@/lib/types";
import { BattlecardView } from "./Battlecard";

const report = { company: "Acme", run_date: "2026-10-05", notes: {}, views: { names: ["Acme", "Rival"], categories: [
  { id: "pricing", label: "Pricing & value", basis: "1 capability", leader: "Rival", scores: { Rival: 1, Acme: 0 }, detail: { Rival: "Published pricing: full", Acme: "Published pricing: none" } },
  { id: "support", label: "Support", basis: "1 capability", leader: "Acme", scores: { Acme: 1, Rival: 0.5 }, detail: {} },
] }, profiles: {
  Acme: { pricing_tiers: [{ name: "Growth", price: "$49/agent/mo", sources: [] }] },
  Rival: { pricing_summary: { text: "Contact sales only." }, recent_changes: [{ text: "Launched AI agent", sources: [] }] },
} } as never;
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
  it("leads with when we win, when we lose and what to say", () => {
    const c = { ...card, tldr: "We win on speed. We lose when brand matters." } as Battlecard;
    render(<BattlecardView report={report} card={c} view={view} index={new Map()} />);
    expect(screen.getByText("We win on speed.")).toBeInTheDocument();
    expect(screen.getByText("We lose when brand matters.")).toBeInTheDocument();
    expect(screen.getByText("“Say this.”")).toBeInTheDocument();
    expect(screen.getByText("Fast setup")).toBeInTheDocument();
    expect(screen.getByText(/Ask for references/)).toBeInTheDocument();
    expect(screen.queryByText(/we lead/i)).not.toBeInTheDocument(); // no tally repeated on the card
  });
  it("hides empty sections instead of listing them", () => {
    const empty = { ...view, ratings: [], known: 0, tally: { lead: 0, even: 0, behind: 0, unknown: 0 }, evidence: { total: 0, independent: 0, pct: 0, items: 0, top_site_items: 0 } } as CardView;
    render(<BattlecardView report={report} card={{ ...card, where_we_win: [], where_we_lose: [] }} view={empty} index={new Map()} />);
    expect(screen.queryByText("Our edge")).not.toBeInTheDocument();
    expect(screen.queryByText("If they say…")).not.toBeInTheDocument();
    expect(screen.getByText(/Not enough evidence yet/)).toBeInTheDocument();
  });
  it("keeps the proof one click away: quote, source, our read", () => {
    const index = new Map([["S1", { id: "S1", company: "Rival", category: "reviews", url: "https://www.g2.com/r",
      title: "G2", origin: "independent", kind: "review", published: "2026-08-01" }]]) as never;
    const layered = { ...card, where_we_win: [{
      headline: "Live in a day", support: "single_source", sources: ["S1"],
      evidence: [{ source: "S1", text: "Setup took a single afternoon" }],
      analysis: "Fast time to value for small teams.", use: "Ask how long their last rollout took.",
    }] } as unknown as Battlecard;
    const view2 = { ...view, evidence: { ...view.evidence, top_site: "g2.com", top_site_items: 3, items: 4 } } as CardView;
    render(<BattlecardView report={report} card={layered} view={view2} index={index} />);
    expect(screen.getByText("Live in a day").closest("summary")).not.toBeNull();
    expect(screen.getByText("Ask how long their last rollout took.")).toBeInTheDocument();
    expect(screen.getByText("“Setup took a single afternoon”")).toBeInTheDocument();
    expect(screen.getByText("g2.com ↗")).toHaveAttribute("href", "https://www.g2.com/r");
    expect(screen.getByText("Fast time to value for small teams.")).toBeInTheDocument();
    expect(screen.getByText(/3 of 4 insights rest on/)).toBeInTheDocument();
    expect(screen.getByText("$49/agent/mo")).toBeInTheDocument();
    expect(screen.getByText("Launched AI agent")).toBeInTheDocument();
  });
  it("shows the top 3 and keeps the rest one click away", () => {
    const many = { ...card, where_we_win: ["A", "B", "C", "D", "E"].map((h) => ({ headline: h, sources: [] })) } as unknown as Battlecard;
    render(<BattlecardView report={report} card={many} view={view} index={new Map()} />);
    expect(screen.getByText("+2 more")).toBeInTheDocument();
    expect(screen.getByText("E").closest("details")).not.toBeNull();
  });
  it("opens with a visual deal brief: threat gauge, where it's decided, three moves", () => {
    const v = { ...view, edges: { pricing: 1, support: -0.5, product: null } } as unknown as CardView;
    const { container } = render(<BattlecardView report={report} card={card} view={v} index={new Map()} deal={{ role: "economic" }} />);
    expect(screen.getByRole("img", { name: /^Threat in this deal: \w+, \d+ of 100$/ })).toBeInTheDocument();
    const rows = [...container.querySelectorAll(".dbl-row:not(.dbl-h) .dbl-name")].map((r) => r.textContent);
    expect(rows).toEqual(["Pricing & value", "Support"]);              // finance buyer: pricing first
    expect(container.querySelector(".dbl-row.hot .dbl-name")).toHaveTextContent("Pricing & value");
    expect(container.querySelectorAll(".db-moves li")).toHaveLength(3);
    expect(screen.getByText("Talk total cost and payback, not list price")).toBeInTheDocument();
    expect(screen.getByText("Finance / budget owner")).toBeInTheDocument();  // applied filter shown as a chip
  });
  it("tailors to the deal: stage sets the order, buyer sets which points come first", () => {
    const c = { ...card,
      where_we_win: [{ headline: "Faster reporting", sources: [] }, { headline: "Lower total cost", sources: [] }],
      landmines: [{ question: "Who owns support?", why: "", sources: [] }],
      objections: [{ objection: "They're cheaper", response: "Compare total cost.", sources: [] }] } as unknown as Battlecard;
    const v = { ...view, tags: { wins: ["product", "pricing"], losses: ["product"], asks: ["support"], objections: ["pricing"] } } as unknown as CardView;
    const { container } = render(<BattlecardView report={report} card={c} view={v} index={new Map()}
                                                 deal={{ stage: "proposal", role: "economic" }} />);
    const heads = [...container.querySelectorAll(".objs > h3, .col > h3")].map((h) => h.textContent);
    expect(heads.slice(0, 3)).toEqual(["If they say…", "Pricing", "Our edge"]);
    const wins = [...container.querySelectorAll(".col.win > ul > .pt .pt-title")].map((t) => t.textContent);
    expect(wins).toEqual(["Lower total costPricing & value"]);  // only the deal-relevant point up front…
    expect(screen.getByText("+1 less relevant to this deal")).toBeInTheDocument(); // …the rest on request
    expect(screen.getByText("Handle objections before price comes up")).toBeInTheDocument();
  });
});
