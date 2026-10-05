import type { Report } from "@/lib/types";
import { ratingText } from "@/lib/report";
import { Glyph, GlyphKey } from "./Primitives";

export function Overview({ report }: { report: Report }) {
  const v = report.views;
  return (
    <section className="ov">
      <div className="facts">
        {v.names.map((name) => {
          const f = report.facts?.[name] ?? {};
          const domain = report.profiles[name]?.domain;
          const any = f.founded || f.headquarters || f.employees || f.owner;
          return (
            <div className="box fact" key={name}>
              <h3>{name}{name === report.company && <span className="us-tag" title="Your company">YOU</span>}</h3>
              <dl>
                {domain && <><dt>Website</dt><dd>{domain}</dd></>}
                {f.founded && <><dt>Founded</dt><dd>{f.founded}</dd></>}
                {f.headquarters && <><dt>HQ</dt><dd>{f.headquarters}</dd></>}
                {f.employees && <><dt>Employees</dt><dd>{f.employees}</dd></>}
                {f.owner && <><dt>Owner</dt><dd>{f.owner}</dd></>}
                {!any && <><dt>Facts</dt><dd className="empty">No Wikipedia entry</dd></>}
              </dl>
              {f.wikipedia && <div className="a" style={{ marginTop: 8 }}><a href={f.wikipedia} target="_blank" rel="noopener">Wikipedia ↗</a></div>}
            </div>
          );
        })}
      </div>

      {v.matrix.length > 0 && (
        <div className="box">
          <div className="label">Capability comparison <span className="hint">· hover a dot for details</span></div>
          <div className="grid-wrap"><table className="grid"><tbody>
            <tr><th className="first">Capability</th>{v.names.map((n) => <th key={n} className={n === report.company ? "is-us" : undefined}>{n}</th>)}</tr>
            {v.matrix.map((cap) => (
              <tr key={cap.name}><td className="first">{cap.name}</td>
                {cap.cells.map((c) => <td key={c.company}><Glyph cell={c} /></td>)}</tr>
            ))}
          </tbody></table></div>
          <GlyphKey />
        </div>
      )}

      {v.sites.length > 0 && (
        <div className="box">
          <div className="label">Review-site ratings <span className="hint">· independent review sites only</span></div>
          <div className="grid-wrap"><table className="grid"><tbody>
            <tr><th className="first">Company</th>{v.sites.map((s) => <th key={s}>{s}</th>)}</tr>
            {v.market_ratings.map((row) => (
              <tr key={row.name} className={row.name === report.company ? "is-us" : undefined}>
                <td className="first">{row.name}</td>
                {v.sites.map((s) => {
                  const x = row.by_site[s];
                  return (
                    <td key={s}>{x ? (<>
                      <div className="rcell" data-tip={`${row.name} on ${s}: ${ratingText(x)}`}>
                        <b>{x.rating}{(x.out_of ?? 5) !== 5 && <span className="of">/{x.out_of}</span>}</b>
                        <div className="rbar"><span style={{ width: `${Math.round((x.rating / (x.out_of ?? 5)) * 100)}%` }} /></div>
                        {x.review_count ? <small>{x.review_count.toLocaleString("en-US")} reviews</small> : null}
                      </div></>) : <span className="empty">–</span>}</td>
                  );
                })}
              </tr>
            ))}
          </tbody></table></div>
        </div>
      )}
    </section>
  );
}
