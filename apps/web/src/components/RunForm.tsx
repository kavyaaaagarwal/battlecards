"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

type Row = { name: string; domain: string };
const blank: Row = { name: "", domain: "" };

export function RunForm() {
  const router = useRouter();
  const [company, setCompany] = useState<Row>(blank);
  const [rivals, setRivals] = useState<Row[]>([blank, blank]);
  const [category, setCategory] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function fillExample() {
    setCompany({ name: "Netchex", domain: "netchex.com" });
    setRivals([
      { name: "Paylocity", domain: "paylocity.com" }, { name: "isolved", domain: "isolvedhcm.com" }, { name: "Paycor", domain: "paycor.com" },
    ]);
    setCategory("HCM software");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    const res = await fetch("/api/runs", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ company, competitors: rivals.filter((r) => r.name.trim()), category }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok) router.push(`/reports/${data.run_id}`);
    else { setError(data.error ?? "Something went wrong."); setBusy(false); }
  }

  const field = (row: Row, set: (r: Row) => void, label: string) => (
    <div className="form-row">
      <input aria-label={`${label} name`} placeholder="Company name" value={row.name} onChange={(e) => set({ ...row, name: e.target.value })} />
      <input aria-label={`${label} domain`} placeholder="domain.com (optional)" value={row.domain} onChange={(e) => set({ ...row, domain: e.target.value })} />
    </div>
  );

  return (
    <form className="box run-form" onSubmit={submit}>
      <div className="label">Your company <button type="button" className="link-btn" onClick={fillExample}>Try an example</button></div>
      {field(company, setCompany, "Your company")}
      <div className="label" style={{ marginTop: 14 }}>Competitors <span className="hint">· up to 4</span></div>
      {rivals.map((r, i) => (
        <div key={i}>{field(r, (v) => setRivals(rivals.map((x, j) => (j === i ? v : x))), `Competitor ${i + 1}`)}</div>
      ))}
      {rivals.length < 4 && <button type="button" className="btn" onClick={() => setRivals([...rivals, blank])}>+ Add competitor</button>}
      <div className="label" style={{ marginTop: 14 }}>Category <span className="hint">· helps disambiguate names</span></div>
      <input aria-label="Category" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="e.g. cruise booking software (optional)" />
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="btn primary" type="submit" disabled={busy}>{busy ? "Starting…" : "Research this market"}</button>
      <p className="hint" style={{ marginTop: 8 }}>Takes about 3-5 minutes. Uses free AI models and search, so a run may occasionally need a retry.</p>
    </form>
  );
}
