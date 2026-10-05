import type { Battlecard, CardView, Report } from "@/lib/types";
import { type SourceIndex, VERDICT_LABEL } from "@/lib/report";
import { PrintButton } from "./ClientBits";
import { Glance } from "./Glance";
import { EvidenceBadge, Glyph, GlyphKey } from "./Primitives";

type Props = { report: Report; card: Battlecard; view: CardView; index: SourceIndex };

export function BattlecardView({ report, card, view, index }: Props) {
  const us = report.company, them = card.competitor;
  const note = report.notes?.[them];
  return (
    <article className="bc">
      <div className="bc-head">
        <div><h2>{us} <span>vs</span> {them}</h2>{card.overview && <div className="overview">{card.overview}</div>}</div>
        <div className="bc-tools"><span className="updated">Updated {report.run_date}</span><PrintButton /></div>
      </div>

      <Glance us={us} them={them} view={view} />

      <div className="lead">
        <div><div className="label">Bottom line</div><div className="bottom-line">{card.tldr}</div></div>
        <div className="say">
          {card.quick_dismiss
            ? (<><div className="label">Quick dismiss <span className="hint">· say this when they come up</span></div><p>“{card.quick_dismiss}”</p></>)
            : card.pricing_comparison && (<><div className="label">Pricing</div><p>{card.pricing_comparison.text}</p></>)}
        </div>
      </div>

      {view.rows.length > 0 && (
        <div className="matrix">
          <div className="label">Feature comparison</div>
          <table className="cmp"><tbody>
            <tr><th>Capability</th><th className="us">{us}</th><th className="them">{them}</th><th /></tr>
            {view.rows.map((row) => (
              <tr key={row.name}>
                <td className="cap">{row.name}</td>
                <td className="st"><Glyph cell={row.us} />{row.us.note && <span className="cnote">{row.us.note}</span>}</td>
                <td className="st"><Glyph cell={row.them} />{row.them.note && <span className="cnote">{row.them.note}</span>}</td>
                <td className={`verdict v-${row.verdict}`}>{VERDICT_LABEL[row.verdict]}</td>
              </tr>
            ))}
          </tbody></table>
          <GlyphKey />
        </div>
      )}

      <div className="row">
        <div className="cell win">
          <div className="label">✓ Why we win</div>
          <ul className="points">
            {card.where_we_win?.length ? card.where_we_win.map((x, i) => (
              <li key={i}><div className="hl">{x.headline}<EvidenceBadge ids={x.sources} index={index} /></div>
                {x.detail && <div className="detail">{x.detail}</div>}</li>
            )) : <li className="empty">Not enough evidence yet.</li>}
          </ul>
        </div>
        <div className="cell lose">
          <div className="label">⚠ Where they&apos;re strong <span className="hint">· and how to counter</span></div>
          <ul className="points">
            {card.where_we_lose?.length ? card.where_we_lose.map((x, i) => (
              <li key={i}><div className="hl">{x.headline}<EvidenceBadge ids={x.sources} index={index} /></div>
                {x.detail && <div className="detail">{x.detail}</div>}
                {x.counter && <div className="counter"><b>Counter:</b> {x.counter}</div>}</li>
            )) : <li className="empty">Not enough evidence yet.</li>}
          </ul>
        </div>
      </div>

      {(card.landmines?.length || card.objections?.length) ? (
        <div className="row">
          <div className="cell">
            <div className="label">Landmines <span className="hint">· questions to ask the prospect</span></div>
            <ul className="qa">{card.landmines?.length ? card.landmines.map((x, i) => (
              <li key={i}><div className="q">“{x.question}”</div><div className="a">{x.why}<EvidenceBadge ids={x.sources} index={index} /></div></li>
            )) : <li className="empty">None backed by independent evidence.</li>}</ul>
          </div>
          <div className="cell">
            <div className="label">Objections <span className="hint">· they say → you say</span></div>
            <ul className="qa">{card.objections?.length ? card.objections.map((x, i) => (
              <li key={i}><div className="they">“{x.objection}”</div><div className="we"><b>→</b> {x.response}</div></li>
            )) : <li className="empty">None documented.</li>}</ul>
          </div>
        </div>
      ) : null}

      {((card.quick_dismiss && card.pricing_comparison) || card.proof_quotes?.length) ? (
        <div className="row">
          <div className="cell">
            <div className="label">Pricing</div>
            {card.quick_dismiss && card.pricing_comparison
              ? <div>{card.pricing_comparison.text}</div>
              : <div className="empty">See bottom line.</div>}
          </div>
          <div className="cell">
            <div className="label">Proof <span className="hint">· real customers, independent sites</span></div>
            {card.proof_quotes?.length ? card.proof_quotes.map((q, i) => <div className="quote" key={i}>“{q.quote}”</div>)
              : <div className="empty">No independent quotes this run.</div>}
          </div>
        </div>
      ) : null}

      {note && <div className="note"><div className="label">Analyst take</div><p style={{ whiteSpace: "pre-wrap" }}>{note}</p></div>}
    </article>
  );
}
