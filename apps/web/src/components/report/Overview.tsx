import { Fragment } from "react";
import type { Report } from "@/lib/types";
import { CATEGORY_IDS, type Deal } from "@/lib/deal";
import { ratingText, shortDate } from "@/lib/report";
import { Glyph, GlyphKey } from "./Primitives";
import { Reputation } from "./Reputation";
import { ThreatMap } from "./ThreatMap";
import { RatingTrend } from "./Trends";

type Item = { key: string; tag: string; tone: string; company: string; text: string; then?: string | null };

/** Everything that moved since the last report, most consequential first: high-severity changes,
 *  then measured moves (computed in code from verified numbers), then the rest. */
function changeItems(report: Report): Item[] {
  const changes = report.changes?.changes ?? [];
  const sig = report.history?.signals ?? [];
  const ch = (sev: string) => changes.filter((c) => c.severity === sev).map((c, i) => ({
    key: `c-${sev}-${i}`, tag: sev, tone: sev, company: c.company, text: c.change,
    then: c.rep_action || c.why_it_matters,
  }));
  const measured = sig.map((s, i) => ({
    key: `s-${i}`, tag: "measured", tone: s.good_for_us === true ? "good" : s.good_for_us === false ? "bad" : "neutral",
    company: s.company, text: s.text, then: null,
  }));
  return [...ch("high"), ...measured, ...ch("medium"), ...ch("low")];
}

function ChangeList({ items }: { items: Item[] }) {
  /** One line each; the full change and what to do open on click. */
  const row = (x: Item) => {
    const tag = <span className={`ctag ${x.tag}`}>{x.tag === "measured" ? (x.tone === "good" ? "▲ good for us" : x.tone === "bad" ? "▼ watch" : "measured") : x.tag}</span>;
    const line = <div className="chg-line"><b>{x.company}</b> · {x.text}</div>;
    return (
      <li key={x.key} className={`chg t-${x.tone}`}>
        {x.then ? (
          <details>
            <summary>{tag}{line}</summary>
            <div className="chg-do"><b>Do:</b> {x.then}</div>
          </details>
        ) : <div className="chg-row">{tag}{line}</div>}
      </li>
    );
  };
  return (
    <ul className="chgs">
      {items.slice(0, 3).map(row)}
      {items.length > 3 && (
        <li className="more-pts"><details><summary>+{items.length - 3} more changes</summary><ul className="chgs">{items.slice(3).map(row)}</ul></details></li>
      )}
    </ul>
  );
}

export function Overview({ report, deal }: { report: Report; deal: Deal }) {
  const v = report.views;
  const points = report.history?.points ?? [];
  const prev = points.length > 1 ? points[points.length - 2].run_date : report.previous_run;
  const items = changeItems(report);
  const label = Object.fromEntries((v.categories ?? []).map((c) => [c.id, c.label]));
  const matrix = [...v.matrix].sort((a, b) =>
    CATEGORY_IDS.indexOf(a.category as never) - CATEGORY_IDS.indexOf(b.category as never));

  return (
    <section className="ov">
      <ThreatMap report={report} deal={deal} />
      <Reputation report={report} />

      {(items.length > 0 || prev) && (
        <div className="box">
          <div className="ov-h">
            <h3>What changed</h3>
            {prev && <span>{shortDate(prev)} → {shortDate(report.run_date)}</span>}
          </div>
          {items.length ? <ChangeList items={items} /> : <p className="empty">Nothing meaningful moved since the last report.</p>}
        </div>
      )}

      {points.length > 1 && (
        <details className="box full">
          <summary>Rating history <span>{points.length} reports · {shortDate(points[0].run_date)} – {shortDate(report.run_date)}</span></summary>
          <div className="trends full-sec">
            {report.competitors.map((them) => (
              <div className="trend" key={them}>
                <h4>{report.company} vs {them}</h4>
                <RatingTrend us={report.company} them={them} points={points} />
              </div>
            ))}
          </div>
        </details>
      )}

      <details className="box full">
        <summary>Full comparison <span>every capability · every review site</span></summary>
        {matrix.length > 0 && (
          <div className="full-sec">
            <div className="grid-wrap"><table className="grid"><tbody>
              <tr><th className="first">Capability</th>{v.names.map((n) => <th key={n} className={n === report.company ? "is-us" : undefined}>{n}</th>)}</tr>
              {matrix.map((cap, i) => (<Fragment key={cap.name}>
                {cap.category !== matrix[i - 1]?.category && (
                  <tr className="cat-row"><td colSpan={v.names.length + 1}>{label[cap.category] ?? cap.category}</td></tr>
                )}
                <tr><td className="first">{cap.name}</td>
                  {cap.cells.map((c) => <td key={c.company}><Glyph cell={c} /></td>)}</tr>
              </Fragment>))}
            </tbody></table></div>
            <GlyphKey />
          </div>
        )}
        {v.sites.length > 0 && (
          <div className="full-sec">
            <div className="label">Review-site ratings <span className="hint">· independent review sites only</span></div>
            <div className="grid-wrap"><table className="grid"><tbody>
              <tr><th className="first">Company</th>{v.sites.map((s) => <th key={s}>{s}</th>)}</tr>
              {v.market_ratings.map((row) => (
                <tr key={row.name} className={row.name === report.company ? "is-us" : undefined}>
                  <td className="first">{row.name}</td>
                  {v.sites.map((s) => {
                    const x = row.by_site[s];
                    return <td key={s}>{x ? ratingText(x) : <span className="empty">–</span>}</td>;
                  })}
                </tr>
              ))}
            </tbody></table></div>
          </div>
        )}
      </details>
    </section>
  );
}
