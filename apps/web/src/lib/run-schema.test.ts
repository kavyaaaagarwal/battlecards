import { describe, expect, it } from "vitest";
import { RunInput, toIntelBody } from "./run-schema";

const ok = { company: { name: " Acme ", domain: "" }, competitors: [{ name: "Rival", domain: "rival.io" }], category: "help desk" };

describe("RunInput", () => {
  it("accepts a normal request and drops empty domains", () => {
    const v = RunInput.parse(ok);
    expect(toIntelBody(v)).toEqual({ company: { name: "Acme" }, competitors: [{ name: "Rival", domain: "rival.io" }], category: "help desk" });
  });
  it.each([
    [{ ...ok, competitors: [] }, "Add at least one competitor"],
    [{ ...ok, competitors: Array.from({ length: 5 }, (_, i) => ({ name: `C${i}` })) }, "Up to 4 competitors"],
    [{ ...ok, competitors: [{ name: "acme" }] }, "must all be different"],
    [{ ...ok, company: { name: "  " } }, "Company name is required"],
  ])("rejects bad input %#", (input, message) => {
    const r = RunInput.safeParse(input);
    expect(r.success).toBe(false);
    expect(r.error!.issues[0].message).toContain(message);
  });
});
