import type { Report } from "@/lib/types";
import { companyColor, Donut } from "./Charts";

/** Digital reputation at a glance, as its two halves: how many customers are talking (share of
 *  all reviews found) and how happy they are (rating after the pull to each site's average, so a
 *  handful of glowing reviews can't outrank thousands). */
export function Reputation({ report }: { report: Report }) {
  const v = report.views;
  const cat = (id: string) => (v.categories ?? []).find((c) => c.id === id);
  const rating = cat("rating"), voice = cat("voice");
  const rows = v.names.map((name) => ({
    name, reviews: voice?.values?.[name] ?? 0, rating: rating?.values?.[name] ?? null,
    thin: !!rating?.thin?.includes(name), detail: rating?.detail[name] ?? "", color: companyColor(v.names, name),
  }));
  const total = rows.reduce((s, r) => s + r.reviews, 0);
  const rated = rows.filter((r) => r.rating !== null).sort((a, b) => b.rating! - a.rating!);
  if (!total && !rated.length) return null;
  const lo = Math.floor(Math.min(...rated.map((r) => r.rating!), 4) * 2) / 2 - 0.5;
  const pct = (x: number) => ((x - lo) / (5 - lo)) * 100;
  const fmt = (n: number) => n.toLocaleString("en-US");

  return (
    <div className="box rep">
      <div className="ov-h"><h3>Digital reputation</h3><span>independent review sites only</span></div>
      <div className="rep-grid">
        {total > 0 && (
          <div className="rep-voice">
            <div className="label">Share of reviews</div>
            <div className="rep-donut">
              <Donut center={fmt(total)} sub="reviews" slices={rows.filter((r) => r.reviews).map((r) => ({
                key: r.name, value: r.reviews, color: r.color,
                tip: `${r.name}: ${fmt(r.reviews)} reviews (${Math.round((100 * r.reviews) / total)}%)`,
              }))} />
              <ul className="rep-legend">
                {rows.filter((r) => r.reviews).sort((a, b) => b.reviews - a.reviews).map((r) => (
                  <li key={r.name} className={r.name === report.company ? "is-us" : undefined}>
                    <i className="sw" style={{ background: r.color }} />{r.name}
                    <b>{Math.round((100 * r.reviews) / total)}%</b>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {rated.length > 0 && (
          <div className="rep-rating">
            <div className="label">Fair rating <span className="hint">· out of 5, few reviews pull toward the site average</span></div>
            <div className="rep-rows">
              {rated.map((r) => (
                <div key={r.name} className={`rep-row${r.name === report.company ? " is-us" : ""}${r.thin ? " thin-row" : ""}`}
                     data-tip={`${r.name}: ${r.detail}${r.thin ? " · Low confidence: under 50 reviews, so this sits close to average" : ""}`}>
                  <span className="rep-name">{r.name}{r.thin && <i className="thin static" aria-label="low confidence">?</i>}</span>
                  <span className="rep-track"><span className="rep-dot" style={{ left: `${pct(r.rating!)}%`, background: r.color }} /></span>
                  <b className="rep-val">{r.rating!.toFixed(1)}</b>
                </div>
              ))}
              <div className="rep-row rep-axis" aria-hidden="true"><span /><span className="raxis"><span>{lo}</span><span>5</span></span><span /></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
