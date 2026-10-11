import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DealBar } from "./DealBar";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }), usePathname: () => "/reports/abc" }));

describe("DealBar", () => {
  it("waits for Apply, then applies the whole combination at once", () => {
    render(<DealBar deal={{}} tab="rival" />);
    const apply = screen.getByRole("button", { name: "Apply" });
    expect(apply).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Key buyer"), { target: { value: "economic" } });
    fireEvent.change(screen.getByLabelText("Stage"), { target: { value: "proposal" } });
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByText("Not applied yet")).toBeInTheDocument();
    fireEvent.click(apply);
    expect(replace).toHaveBeenCalledWith("/reports/abc?tab=rival&stage=proposal&role=economic", { scroll: false });
  });
});
