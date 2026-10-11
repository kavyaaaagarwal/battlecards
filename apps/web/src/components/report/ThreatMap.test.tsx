import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ThreatMap } from "./ThreatMap";

const report = {
  id: "abc", company: "Acme",
  battlecards: [{ competitor: "Big" }, { competitor: "Small" }],
  views: {
    cards: [{ edges: { pricing: 0.5, support: -0.3 } }, { edges: { pricing: -1, support: -1 } }],
    categories: [
      { id: "pricing", label: "Pricing & value", basis: "1 capability", leader: "Big", scores: {}, detail: {} },
      { id: "support", label: "Support", basis: "1 capability", leader: "Acme", scores: {}, detail: { Acme: "Support: full" } },
      { id: "integrations", label: "Integrations & IT", basis: "no evidence", leader: null, scores: {}, detail: {} },
      { id: "rating", label: "Rating", basis: "1 review site", leader: null, scores: {}, detail: {}, thin: ["Acme"] },
    ],
  },
} as never;

describe("ThreatMap", () => {
  it("ranks the biggest threat first and names who leads each category", () => {
    const { container } = render(<ThreatMap report={report} deal={{}} />);
    expect(screen.getByText(/Biggest threat:/).textContent).toContain("Big · ahead of us on Pricing & value");
    expect([...container.querySelectorAll("tbody th a")].map((a) => a.textContent)).toEqual(["Big →", "Small →"]);
    expect(screen.getByText("Big lead")).toBeInTheDocument();
    expect(screen.getByText("You lead")).toBeInTheDocument();
    expect(screen.queryByText("Integrations & IT")).not.toBeInTheDocument(); // no evidence, no column
  });
  it("highlights the categories a deal weighs and keeps the filters in links", () => {
    const { container } = render(<ThreatMap report={report} deal={{ role: "economic" }} />);
    expect(screen.getByText("Pricing & value").closest("th")).toHaveClass("focus");
    expect(container.querySelector("tbody th a")).toHaveAttribute("href", "/reports/abc?tab=big&role=economic");
  });
  it("marks ratings that rest on too few reviews", () => {
    render(<ThreatMap report={report} deal={{}} />);
    expect(screen.getByText("Rating rests on under 50 reviews")).toBeInTheDocument();
    expect(screen.getAllByLabelText("low confidence").length).toBeGreaterThan(0);
  });
});
