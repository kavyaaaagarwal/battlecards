import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RequestForm } from "./RequestForm";

afterEach(() => vi.unstubAllGlobals());

describe("RequestForm", () => {
  it("registers interest and thanks the visitor, without starting a run", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    vi.stubGlobal("fetch", fetch);
    render(<RequestForm />);
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "Asha Rao" } });
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "asha@acme.com" } });
    fireEvent.change(screen.getByLabelText("Company"), { target: { value: "Acme" } });
    fireEvent.change(screen.getByLabelText(/Competitors you.d compare against/), { target: { value: "Zendesk" } });
    fireEvent.click(screen.getByRole("button", { name: "Register interest" }));

    expect(await screen.findByText("Thanks, Asha.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/requests", expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({ company: "Acme", competitors: "Zendesk" });
  });
});
