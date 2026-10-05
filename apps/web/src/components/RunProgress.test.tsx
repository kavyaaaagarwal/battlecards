import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RunStatus } from "@/lib/types";
import { RunProgress } from "./RunProgress";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const base = { id: "0123456789", created_at: "", company: "Acme", competitors: ["Rival"], degraded: false, current_stage: null };

describe("RunProgress", () => {
  it("shows each stage's state and notes", () => {
    const initial = { ...base, status: "running", progress: [
      { stage: "collect", status: "done", at: "", note: "45 sources, 20 independent" },
      { stage: "profiles", status: "running", at: "", note: "" },
    ] } as RunStatus;
    render(<RunProgress runId="0123456789" initial={initial} />);
    expect(screen.getByText("Collecting sources")).toBeInTheDocument();
    expect(screen.getByText("45 sources, 20 independent")).toBeInTheDocument();
    expect(screen.getByText("Profiling companies").closest("li")).toHaveClass("running");
  });
  it("explains a failed run instead of spinning forever", () => {
    const initial = { ...base, status: "failed", error: "The profiles step failed: model down", progress: [] } as RunStatus;
    render(<RunProgress runId="0123456789" initial={initial} />);
    expect(screen.getByRole("alert")).toHaveTextContent("model down");
    expect(screen.getByRole("link", { name: /try again/i })).toHaveAttribute("href", "/");
  });
  it("tells the user when a run has stopped making progress", () => {
    const old = "2000-01-01T00:00:00+00:00";
    const initial = { ...base, created_at: old, status: "running", progress: [
      { stage: "collect", status: "running", at: old, note: "" },
    ] } as RunStatus;
    render(<RunProgress runId="0123456789" initial={initial} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/stuck/i);
  });
});
