import Link from "next/link";
import type { CategoryView, Report } from "@/lib/types";
import { type Deal, dealQuery, focus, threat, threatLevel } from "@/lib/deal";
import { slug } from "@/lib/report";

const EDGE = 0.1; // smaller gaps read as even
type Edge = "ahead" | "behind" | "even" | "none";
const edgeOf = (e: number | null | undefined): Edge =>
  e === null || e === undefined ? "none" : e > EDGE ? "ahead" : e < -EDGE ? "behind" : "even";
const MARK: Record<Edge, string> = { ahead: "▲", behind: "▼", even: "=", none: "–" };
const SAYS: Record<Edge, string> = { ahead: "they're ahead", behind: "we're ahead", even: "even", none: "no evidence" };
const LEVEL = { high: "High", medium: "Medium", low: "Low", unknown: "Unclear" } as const;

function cellTip(cat: CategoryView, us: string, them: string, edge: Edge) {
  const d = (n: string) => cat.detail[n] || "no evidence";
  const thin = [them, us].filter((n) => cat.thin?.includes(n));
  return `${cat.label}, ${them} vs ${us}: ${SAYS[edge]} · ${them}: ${d(them)} · ${us}: ${d(us)}`
    + (thin.length ? ` · Low confidence: ${thin.join(" and ")} ${thin.length > 1 ? "have" : "has"} under 50 reviews` : "");
}

/** Who leads each buying category, and which competitor is the biggest threat for this deal. */
export function ThreatMap({ report, deal }: { report: Report; deal: Deal }) {
  const v = report.views;
  const cats = (v.categories ?? []).filter((c) => c.basis !== "no evidence");
  const us = report.company;
  const focused = new Map(focus(deal).map((f) => [f.id, f.why]));
  const rows = report.battlecards.map((card, i) => {
    const edges = v.cards[i]?.edges ?? {};
    const t = threat(edges, deal);
    return { name: card.competitor, edges, t, level: threatLevel(t) };
  }).sort((a, b) => (b.t ?? -1) - (a.t ?? -1));

  if (!cats.length) return null;
  const top = rows[0];
  const topAhead = top ? cats.filter((c) => edgeOf(top.edges[c.id]) === "ahead").map((c) => c.label) : [];

  return (
    <div className="box tm">
      <div className="ov-h">
        <h3>Who leads where</h3>
        {focused.size > 0 && <span>Weighted for this deal: {[...focused.keys()].map((id) => v.categories?.find((c) => c.id === id)?.label ?? id).join(", ")}</span>}
      </div>
      {top?.t !== null && top && (
        <p className="tm-lead">
          Biggest threat: <b>{top.name}</b>
          {topAhead.length ? <> · ahead of us on {topAhead.join(", ")}</> : <> · not clearly ahead anywhere</>}
        </p>
      )}
      <div className="grid-wrap">
        <table className="tm-grid">
          <thead>
            <tr>
              <th className="first" scope="col"><span className="sr">Competitor</span></th>
              {cats.map((c) => (
                <th key={c.id} scope="col" className={focused.has(c.id) ? "focus" : undefined}
                    data-tip={`${c.label}: scored on ${c.basis}${focused.has(c.id) ? ` · weighted up for ${focused.get(c.id)!.join(", ")}` : ""}`}>
                  {c.label}
                  <small className={c.leader === us ? "is-us" : undefined}>{c.leader ? `${c.leader === us ? "You" : c.leader} lead` : "No clear leader"}</small>
                </th>
              ))}
              <th scope="col" className="tm-th-threat">Threat to us</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name}>
                <th scope="row" className="first">
                  <Link href={`/reports/${report.id}${dealQuery(deal, { tab: slug(r.name) })}`}>{r.name} <span aria-hidden="true">→</span></Link>
                </th>
                {cats.map((c) => {
                  const e = edgeOf(r.edges[c.id]);
                  return (
                    <td key={c.id} className={focused.has(c.id) ? "focus" : undefined}>
                      <span className={`tc e-${e}`} data-tip={cellTip(c, us, r.name, e)} aria-label={`${c.label}: ${SAYS[e]}`}>
                        {MARK[e]}{c.leader === r.name && <i className="lead-star" aria-label="category leader">★</i>}
                        {(c.thin?.includes(r.name) || c.thin?.includes(us)) && <i className="thin" aria-label="low confidence">?</i>}
                      </span>
                    </td>
                  );
                })}
                <td className="tm-threat">
                  <span className={`tbar t-${r.level}`} data-tip="How far ahead of us they are across the categories, weighted for your deal filters (50 = even)">
                    <i style={{ width: `${r.t ?? 0}%` }} />
                  </span>
                  <b className={`tl t-${r.level}`}>{LEVEL[r.level]}</b>
                </td>
              </tr>
            ))}
            <tr className="is-us">
              <th scope="row" className="first">{us} <span className="you">you</span></th>
              {cats.map((c) => (
                <td key={c.id} className={focused.has(c.id) ? "focus" : undefined}>
                  {c.leader === us && <span className="tc e-us" data-tip={`You lead ${c.label}: ${c.detail[us]}`}><i className="lead-star">★</i></span>}
                  {c.thin?.includes(us) && c.leader !== us && <span className="tc e-none" data-tip={`Your ${c.label.toLowerCase()} rests on under 50 reviews: ${c.detail[us]}`}><i className="thin static">?</i></span>}
                </td>
              ))}
              <td />
            </tr>
          </tbody>
        </table>
      </div>
      <div className="tm-key">
        <span><span className="tc e-ahead">▲</span> They&apos;re ahead</span>
        <span><span className="tc e-behind">▼</span> We&apos;re ahead</span>
        <span><span className="tc e-even">=</span> Even</span>
        <span><span className="tc e-none">–</span> No evidence</span>
        <span><i className="lead-star">★</i> Category leader</span>
        {cats.some((c) => c.thin?.length) && <span><i className="thin static">?</i> Rating rests on under 50 reviews</span>}
        <span className="hint">Hover a cell for the evidence</span>
      </div>
    </div>
  );
}
