import type { Report } from "@/lib/types";
import { vendorOf } from "@/lib/report";

const PROFILE_LISTS = [
  ["Reviewers like", "review_strengths"], ["Reviewers complain about", "review_weaknesses"],
  ["Recent changes", "recent_changes"], ["Hiring signals", "hiring_signals"],
] as const;

export function Appendix({ report }: { report: Report }) {
  const pos = report.positioning;
  const changes = report.changes?.changes ?? [];
  return (
    <div className="appendix">
      <h2>For product marketing</h2>
      {report.changes && (
        <details className="sec" open={changes.length > 0}>
          <summary>What changed since last run <span className="sub">vs {report.previous_run} · {changes.length} changes</span></summary>
          <div className="sec-body">
            {changes.map((ch, i) => (
              <div className="change" key={i}><span className={`tag ${ch.severity}`}>{ch.severity}</span><b>{ch.company}:</b> {ch.change}
                <div className="a">Why it matters: {ch.why_it_matters}</div></div>
            ))}
            {!changes.length && <div className="empty">No meaningful changes detected.</div>}
          </div>
        </details>
      )}
      {pos && (
        <details className="sec">
          <summary>Positioning landscape <span className="sub">table stakes, white space, recommended angle</span></summary>
          <div className="sec-body">
            {pos.recommended_angle && (<><h4>Recommended angle for {report.company}</h4>
              <p style={{ margin: 0 }}>{pos.recommended_angle.text}</p></>)}
            <div className="grid2" style={{ marginTop: 8 }}>
              <div><h4>Table stakes · everyone claims this</h4>
                <table className="plain"><tbody>{pos.table_stakes?.map((t) => (
                  <tr key={t.theme}><td>{t.theme}</td><td>{t.companies.join(", ")}</td></tr>))}</tbody></table></div>
              <div><h4>White space · nobody owns this</h4>
                <ul className="qa">{pos.white_space?.map((x) => (
                  <li key={x.opportunity}><div className="q">{x.opportunity}</div><div className="a">{x.evidence}</div></li>))}</ul></div>
            </div>
          </div>
        </details>
      )}
      {Object.entries(report.profiles).map(([name, p]) => (
        <details className="sec" key={name}>
          <summary>{name}{name === report.company && " (us)"} · company snapshot <span className="sub">{p.domain ?? ""}</span></summary>
          <div className="sec-body">
            {p.positioning && <div className="pos">{p.positioning.text}</div>}
            {p.pricing_summary && (<><h4>Pricing</h4><div>{p.pricing_summary.text}</div></>)}
            <div className="grid2">
              {PROFILE_LISTS.map(([label, key]) => (p[key]?.length ?? 0) > 0 && (
                <div key={key}><h4>{label}</h4><ul className="bul">{p[key]!.map((x, i) => <li key={i}>{x.text}</li>)}</ul></div>
              ))}
            </div>
          </div>
        </details>
      ))}
      <details className="sec" id="sources">
        <summary>Sources <span className="sub">{report.sources.length}</span></summary>
        <div className="sec-body"><ol className="sources">
          {report.sources.map((s) => {
            const v = vendorOf(s);
            return (
              <li id={s.id} key={s.id}><span className="id">{s.id}</span><a href={s.url} target="_blank" rel="noopener">{s.title || s.url}</a>
                <span className="src-meta">{s.company === "_market" ? "Market" : s.company} · {s.category.replace("_", " ")} · {v ? <span style={{ color: "var(--warn)" }}>published by {v}</span> : "independent"}{s.published ? ` · ${s.published.slice(0, 10)}` : ""}</span></li>
            );
          })}
        </ol></div>
      </details>
    </div>
  );
}
