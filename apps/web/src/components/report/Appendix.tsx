import type { Report } from "@/lib/types";
import { KIND_LABEL, vendorOf } from "@/lib/report";
import { Snapshots } from "./Snapshots";

export function Appendix({ report }: { report: Report }) {
  const pos = report.positioning;
  return (
    <div className="appendix">
      <h2>Reference</h2>
      <details className="sec">
        <summary>Company profiles <span className="sub">who they are, ratings, published pricing</span></summary>
        <div className="sec-body"><Snapshots report={report} /></div>
      </details>
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
      <details className="sec" id="sources">
        <summary>Sources <span className="sub">{report.sources.length}</span></summary>
        <div className="sec-body"><ol className="sources">
          {report.sources.map((s) => {
            const v = vendorOf(s);
            return (
              <li id={s.id} key={s.id}><span className="id">{s.id}</span><a href={s.url} target="_blank" rel="noopener">{s.title || s.url}</a>
                <span className="src-meta">{s.company === "_market" ? "Market" : s.company} · {s.category.replace("_", " ")} · {v ? <span style={{ color: "var(--warn)" }}>published by {v}</span> : KIND_LABEL[s.kind] ?? "independent"}{s.published ? ` · ${s.published.slice(0, 10)}` : ""}</span></li>
            );
          })}
        </ol></div>
      </details>
    </div>
  );
}
