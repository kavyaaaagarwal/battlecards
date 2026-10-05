import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RunForm } from "./RunForm";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

describe("RunForm", () => {
  it("starts empty so no example value is submitted by accident", () => {
    render(<RunForm />);
    expect(screen.getByLabelText("Your company name")).toHaveValue("");
    expect(screen.getByLabelText("Category")).toHaveValue("");
    expect(screen.getByLabelText("Category")).toHaveAttribute("placeholder", expect.stringContaining("e.g."));
  });
  it("fills a worked example on request", () => {
    render(<RunForm />);
    fireEvent.click(screen.getByRole("button", { name: /try an example/i }));
    expect(screen.getByLabelText("Your company name")).toHaveValue("Netchex");
    expect(screen.getByLabelText("Category")).toHaveValue("HCM software");
  });
});
