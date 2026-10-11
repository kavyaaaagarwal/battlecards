"use client";
import { useState } from "react";

const EMPTY = { name: "", email: "", company: "", competitors: "", role: "", note: "", website: "" };

/** Beta access is invite-only: this registers interest for review. Nothing runs from here. */
export function RequestForm() {
  const [v, setV] = useState(EMPTY);
  const [error, setError] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setV({ ...v, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState("busy"); setError("");
    const res = await fetch("/api/requests", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(v) });
    const data = await res.json().catch(() => ({}));
    if (res.ok) setState("done");
    else { setError(data.error ?? "Something went wrong. Please try again."); setState("idle"); }
  }

  if (state === "done") {
    return (
      <div className="box run-form req-done" role="status">
        <h3>Thanks, {v.name.split(" ")[0]}.</h3>
        <p>We&apos;ve got your request. We&apos;ll email <b>{v.email}</b> once your access is reviewed.</p>
      </div>
    );
  }

  return (
    <form className="box run-form" onSubmit={submit} aria-label="Register interest">
      <div className="req-h"><h3>Register your interest</h3><p>Takes 30 seconds. We review every request and reply by email.</p></div>
      <div className="form-row">
        <label>Your name<input required value={v.name} onChange={set("name")} autoComplete="name" /></label>
        <label>Work email<input required type="email" value={v.email} onChange={set("email")} autoComplete="email" /></label>
      </div>
      <div className="form-row">
        <label>Company<input required value={v.company} onChange={set("company")} autoComplete="organization" placeholder="e.g. Freshworks" /></label>
        <label><span>Your role <span className="hint">· optional</span></span><input value={v.role} onChange={set("role")} autoComplete="organization-title" placeholder="e.g. Head of Sales" /></label>
      </div>
      <label><span>Competitors you&apos;d compare against <span className="hint">· optional</span></span><input value={v.competitors} onChange={set("competitors")} placeholder="e.g. Zendesk, Intercom, Zoho Desk" /></label>
      <label><span>Anything we should know <span className="hint">· optional</span></span>
        <textarea rows={3} value={v.note} onChange={set("note")} placeholder="What you'd like to use it for" />
      </label>
      <input className="hp" tabIndex={-1} aria-hidden="true" autoComplete="off" value={v.website} onChange={set("website")} name="website" />
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="btn primary" type="submit" disabled={state === "busy"}>{state === "busy" ? "Sending…" : "Register interest"}</button>
      <p className="hint" style={{ marginTop: 8 }}>We only use these details to review your request.</p>
    </form>
  );
}
