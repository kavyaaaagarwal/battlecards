import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SourceIndex } from "@/lib/report";
import { EvidenceBadge, Glyph } from "./Primitives";

const index: SourceIndex = new Map([
  ["S1", { id: "S1", company: "Rival", category: "reviews", url: "https://g2.com/x", title: "G2", origin: "independent" }],
  ["S2", { id: "S2", company: "Acme", category: "pricing", url: "https://acme.com/p", title: "Pricing", origin: "vendor:Acme" }],
] as never);

describe("primitives", () => {
  it("names the backing sites in the badge tooltip instead of footnote numbers", () => {
    render(<EvidenceBadge ids={["S1", "S2"]} index={index} />);
    expect(screen.getByText("Independent")).toHaveAttribute("data-tip", "Backed by independent sources: g2.com, acme.com");
  });
  it("labels evidence as independent when any source is independent", () => {
    render(<EvidenceBadge ids={["S2", "S1"]} index={index} />);
    expect(screen.getByText("Independent")).toBeInTheDocument();
  });
  it("labels vendor-only evidence with the vendor's name", () => {
    render(<EvidenceBadge ids={["S2"]} index={index} />);
    expect(screen.getByText("Acme-stated")).toBeInTheDocument();
  });
  it("marks self-reported matrix cells", () => {
    render(<Glyph cell={{ company: "Acme", status: "full", note: "", sources: ["S2"], self: true } as never} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Full, self-reported");
    expect(screen.getByText("*")).toBeInTheDocument();
  });
});
