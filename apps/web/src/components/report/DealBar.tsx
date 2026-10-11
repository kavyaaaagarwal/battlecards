"use client";
import { usePathname, useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { DEAL_FILTERS, type Deal, dealQuery, isTailored } from "@/lib/deal";

const same = (a: Deal, b: Deal) => DEAL_FILTERS.every((f) => (a[f.key] ?? "") === (b[f.key] ?? ""));

/** Five standard deal filters. The rep sets a combination, then applies it in one go; the applied
 *  deal lives in the URL, so a tailored card can be shared with a teammate. */
export function DealBar({ deal, tab }: { deal: Deal; tab?: string }) {
  const router = useRouter();
  const path = usePathname();
  const [draft, setDraft] = useState<Deal>(deal);
  const [applied, setApplied] = useState<Deal>(deal);
  const [pending, start] = useTransition();
  // A new applied deal from the URL (back button, shared link) resets the draft
  if (!same(applied, deal)) { setApplied(deal); setDraft(deal); }
  const dirty = !same(draft, deal);
  const go = (next: Deal) => start(() => router.replace(`${path}${dealQuery(next, tab ? { tab } : {})}`, { scroll: false }));

  return (
    <form className={`deal${pending ? " busy" : ""}`} aria-label="Tailor to your deal"
          onSubmit={(e) => { e.preventDefault(); if (dirty) go(draft); }}>
      <span className="deal-h">Tailor to your deal</span>
      {DEAL_FILTERS.map((f) => (
        <label key={f.key} className={draft[f.key] ? "set" : undefined}>
          <span>{f.label}</span>
          <select value={draft[f.key] ?? ""} onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value || undefined })}>
            <option value="">Any</option>
            {f.options.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
          </select>
        </label>
      ))}
      <div className="deal-act">
        <button type="submit" className="btn apply" disabled={!dirty || pending}>{pending ? "Applying…" : "Apply"}</button>
        {(isTailored(deal) || isTailored(draft)) && (
          <button type="button" className="link-btn" onClick={() => { setDraft({}); if (isTailored(deal)) go({}); }}>Reset</button>
        )}
      </div>
      {dirty && <span className="deal-note" role="status">Not applied yet</span>}
    </form>
  );
}
