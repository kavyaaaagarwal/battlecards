import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { HistoryPoint } from "@/lib/types";
import { RatingTrend } from "./Trends";

const pt = (date: string, us: number | null, them: number, sc: [number, number, number]) => ({
  run_id: date, run_date: date, companies: {
    Acme: { ratings: us === null ? {} : { G2: { rating: us, out_of: 5, rating5: us } }, tiers: {}, sources: 0, independent: 0 },
    Rival: { ratings: { G2: { rating: them, out_of: 5, rating5: them } }, tiers: {}, sources: 0, independent: 0,
             scorecard: { lead: sc[0], even: sc[1], behind: sc[2], known: sc[0] + sc[1] + sc[2] } },
  },
}) as unknown as HistoryPoint;

describe("trends", () => {
  const points = [pt("2026-10-01", 4.5, 4.4, [3, 2, 0]), pt("2026-10-09", null, 4.2, [2, 2, 1])];
  it("labels only the latest rating and never invents a missing one", () => {
    const { container } = render(<RatingTrend us="Acme" them="Rival" points={points} />);
    expect(screen.getByText("4.2")).toBeInTheDocument();          // latest, labelled
    expect(screen.queryByText("4.4")).not.toBeInTheDocument();    // earlier: dot + tooltip only
    expect(container.querySelectorAll(".rt-dot.us")).toHaveLength(1); // Acme missing on Oct 9 stays missing
    expect(container.querySelector(".rt-dot.them.old")).toHaveAttribute("data-tip", "Rival on G2, Oct 1: 4.4");
  });
});
