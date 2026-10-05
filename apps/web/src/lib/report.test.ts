import { describe, expect, it } from "vitest";
import { ratingPct, ratingText, slug, vendorOf } from "./report";

describe("report helpers", () => {
  it("knows who published a source", () => {
    expect(vendorOf({ origin: "vendor:Netchex" } as never)).toBe("Netchex");
    expect(vendorOf({ origin: "independent" } as never)).toBeNull();
  });
  it("places ratings on a lo..5 axis, normalising /10 scales", () => {
    expect(ratingPct({ rating: 4.5, out_of: 5 } as never, 4)).toBe(50);
    expect(ratingPct({ rating: 9, out_of: 10 } as never, 4)).toBe(50);
    expect(ratingPct(null, 4)).toBe(0);
  });
  it("formats ratings and slugs", () => {
    expect(ratingText({ rating: 9, out_of: 10, review_count: 1320 } as never)).toBe("9/10 · 1,320 reviews");
    expect(slug("Paycor Inc.")).toBe("paycor-inc");
  });
});
