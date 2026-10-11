import { describe, expect, it } from "vitest";
import { dealQuery, focus, parseDeal, rankByDeal, sectionOrder, threat, threatLevel, weights } from "./deal";

describe("deal tailoring", () => {
  it("accepts only known filter values from the URL", () => {
    expect(parseDeal({ role: "economic", stage: "nonsense", tab: "rival" })).toEqual({ role: "economic" });
  });
  it("keeps the tab and drops empty filters in links", () => {
    expect(dealQuery({ role: "technical", stage: undefined }, { tab: "rival" })).toBe("?tab=rival&role=technical");
    expect(dealQuery({})).toBe("");
  });
  it("weights what each buyer cares about and says why", () => {
    const w = weights({ role: "technical", org: "ent" });
    expect(w.integrations).toBe(4);
    expect(w.pricing).toBe(1);
    expect(focus({ role: "technical", org: "ent" })[0]).toEqual({ id: "integrations", why: ["2,000+ staff", "IT / security"] });
    expect(focus({})).toEqual([]);
  });
  it("scores threat from weighted edges only, ignoring unknowns", () => {
    const edges = { pricing: 1, product: -1, support: null };
    expect(threat(edges, {})).toBe(50);                             // ahead on one, behind on one: even
    expect(threat(edges, { role: "economic" })!).toBeGreaterThan(50); // finance buyer: their pricing edge counts more
    expect(threat({ voice: 0.6 }, {})).toBe(80);                    // size counts once, through market voice
    expect(threat({ support: null }, {})).toBeNull();
    expect(threatLevel(70)).toBe("high");
    expect(threatLevel(null)).toBe("unknown");
  });
  it("brings deal-relevant points first, keeping evidence order otherwise", () => {
    expect(rankByDeal(["product", "pricing", "product"], 3, {})).toEqual([0, 1, 2]);
    expect(rankByDeal(["product", "pricing", "product"], 3, { role: "economic" })).toEqual([1, 0, 2]);
  });
  it("orders sections by stage and surfaces pricing only when money is on the table", () => {
    expect(sectionOrder({})).toEqual(["edge", "asks", "objections"]);
    expect(sectionOrder({ stage: "discovery" })[0]).toBe("asks");
    expect(sectionOrder({ stage: "proposal" })).toContain("pricing");
  });
});

import { splitByDeal, steps } from "./deal";

describe("deal playbook", () => {
  it("builds three moves from stage, buyer and situation", () => {
    expect(steps({}, "Rival", "Support", "Pricing & value").map((s) => s.text)).toEqual([
      "Lead with our edge: Support", "Be ready for their edge: Pricing & value", "Use the questions below to expose their gaps"]);
    const m = steps({ stage: "evaluation", role: "technical", motion: "displace" }, "Rival", "Support");
    expect(m.map((s) => s.icon)).toEqual(["demo", "doc", "flag"]);
    expect(m[2].text).toBe("Quantify the cost of staying with Rival");
  });
  it("puts only deal-relevant points up front, unless none match", () => {
    expect(splitByDeal(["product", "pricing", "pricing", "support"], 4, { role: "economic" }))
      .toEqual({ top: [1, 2], rest: [0, 3], tailored: true });
    expect(splitByDeal(["product", "support"], 2, { role: "economic" })).toEqual({ top: [0, 1], rest: [], tailored: false });
  });
});
