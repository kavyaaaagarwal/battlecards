import { describe, expect, it } from "vitest";
import { ReportRequest } from "./request-schema";

const ok = { name: "Asha Rao", email: "asha@acme.com", company: "Acme", competitors: "Zendesk, Intercom" };

describe("ReportRequest", () => {
  it("accepts the basics and fills optional fields", () => {
    expect(ReportRequest.parse(ok)).toEqual({ ...ok, role: "", note: "", website: "" });
  });
  it("needs a real email; competitors are optional", () => {
    expect(ReportRequest.safeParse({ ...ok, email: "asha" }).success).toBe(false);
    expect(ReportRequest.parse({ ...ok, competitors: undefined }).competitors).toBe("");
  });
});
