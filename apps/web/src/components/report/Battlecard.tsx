import type { Battlecard, CardView, CategoryId, Excerpt, Report, Support } from "@/lib/types";
import { type Deal, type Section, focus, sectionOrder, splitByDeal } from "@/lib/deal";
import { type SourceIndex, SUPPORT_LABEL, VERDICT_LABEL, siteOf } from "@/lib/report";
import { companyColor } from "./Charts";
import { PrintButton } from "./ClientBits";
import { DealBrief } from "./DealBrief";
import { Glance } from "./Glance";
import { PricingCompare, SourceSays } from "./Insight";
import { EvidenceBadge, Glyph, GlyphKey } from "./Primitives";

type Props = { report: Report; card: Battlecard; view: CardView; index: SourceIndex; deal?: Deal };

type PointProps = {
  title: string; action?: string | null; actionLabel?: string; support?: Support | null;
  evidence?: Excerpt[] | null; analysis?: string | null; detail?: string | null; sources?: string[] | null;
  fit?: string | null; index: SourceIndex;
};

/** One line to read, one line to say. The proof is one click away, never in the way. */
function Point({ title, action, actionLabel = "Say", support, evidence, analysis, detail, sources, fit, index }: PointProps) {
  const ids = sources ?? [];
  const hasProof = !!evidence?.length || !!analysis || !!detail || ids.length > 0;
  const tip = support ? SUPPORT_LABEL[support].tip : undefined;
  const body = (
    <>
      <div className="pt-title">
        {support && <span className={`dot d-${support}`} data-tip={tip} aria-label={tip} />}
        <span>{title}{fit && <span className="fit" data-tip="Matches what this deal's buyer weighs most">{fit}</span>}</span>
      </div>
      {action && <div className="pt-say"><b>{actionLabel}:</b> {action}</div>}
    </>
  );
  if (!hasProof) return <li className="pt">{body}</li>;
  return (
    <li className="pt">
      <details>
        <summary>{body}</summary>
        <div className="pt-proof">
          {evidence?.length ? <SourceSays evidence={evidence} index={index} />
            : ids.length > 0 && <div className="pt-srcs">Source: {ids.filter((i) => index.has(i)).map((i) => siteOf(index.get(i)!)).join(", ")} <EvidenceBadge ids={ids} index={index} /></div>}
          {(analysis || detail) && <div className="pt-read"><span>Our read</span>{analysis || detail}</div>}
          {support && <div className="pt-sup">{SUPPORT_LABEL[support].label} · {SUPPORT_LABEL[support].tip}</div>}
        </div>
      </details>
    </li>
  );
}

/** The points this deal turns on (or the top 3 by evidence) up front; the rest one click away. */
function Ranked({ items, tags, deal, render }: {
  items: number; tags?: CategoryId[]; deal: Deal; render: (i: number) => React.ReactNode;
}) {
  const { top, rest, tailored } = splitByDeal(tags, items, deal);
  return (
    <ul>
      {top.map(render)}
      {rest.length > 0 && (
        <li className="more-pts"><details><summary>+{rest.length} {tailored ? "less relevant to this deal" : "more"}</summary><ul>{rest.map(render)}</ul></details></li>
      )}
    </ul>
  );
}

function Col({ title, tone, children }: { title: string; tone: string; children: React.ReactNode }) {
  return <section className={`col ${tone}`}><h3>{title}</h3>{children}</section>;
}

export function BattlecardView({ report, card, view, index, deal = {} }: Props) {
  const us = report.company, them = card.competitor;
  const wins = card.where_we_win ?? [], losses = card.where_we_lose ?? [];
  const asks = card.landmines ?? [], objections = card.objections ?? [];
  const catLabel = Object.fromEntries((report.views.categories ?? []).map((c) => [c.id, c.label])) as Record<CategoryId, string>;
  const focused = new Set<string>(focus(deal).map((f) => f.id));
  const tags = view.tags;
  const fit = (list: CategoryId[] | undefined, i: number) => {
    const c = list?.[i];
    return c && focused.has(c) ? catLabel[c] ?? c : null;
  };
  const recent = (report.profiles[them]?.recent_changes ?? []).slice(0, 4);
  const note = report.notes?.[them];
  const sections = sectionOrder(deal);
  const pricingUp = sections.includes("pricing");

  const pricing = (
    <>
      <PricingCompare us={us} them={them} profiles={report.profiles} index={index} />
      {card.pricing_comparison && <p className="detail">{card.pricing_comparison.text}</p>}
    </>
  );

  const render: Record<Section, React.ReactNode> = {
    edge: (wins.length || losses.length) ? (
      <div key="edge" className={`cols cols-${[wins.length, losses.length].filter(Boolean).length}`}>
        {wins.length > 0 && <Col title="Our edge" tone="win">
          <Ranked items={wins.length} tags={tags?.wins} deal={deal} render={(i) => { const x = wins[i]; return (
            <Point key={i} title={x.headline} action={x.use} support={x.support} evidence={x.evidence}
                   analysis={x.analysis} detail={x.detail} sources={x.sources} fit={fit(tags?.wins, i)} index={index} />); }} />
        </Col>}
        {losses.length > 0 && <Col title="Their edge" tone="lose">
          <Ranked items={losses.length} tags={tags?.losses} deal={deal} render={(i) => { const x = losses[i]; return (
            <Point key={i} title={x.headline} action={x.counter} actionLabel="Counter" support={x.support}
                   evidence={x.evidence} analysis={x.analysis} detail={x.detail} sources={x.sources} fit={fit(tags?.losses, i)} index={index} />); }} />
        </Col>}
      </div>
    ) : null,
    asks: asks.length ? (
      <section key="asks" className="objs ask">
        <h3>Ask the prospect</h3>
        <Ranked items={asks.length} tags={tags?.asks} deal={deal} render={(i) => { const x = asks[i]; return (
          <Point key={i} title={`“${x.question}”`} support={x.support} evidence={x.evidence}
                 analysis={x.why} sources={x.sources} fit={fit(tags?.asks, i)} index={index} />); }} />
      </section>
    ) : null,
    objections: objections.length ? (
      <section key="objections" className="objs">
        <h3>If they say…</h3>
        <Ranked items={objections.length} tags={tags?.objections} deal={deal} render={(i) => { const x = objections[i]; return (
          <Point key={i} title={`“${x.objection}”`} action={x.response} actionLabel="You say" support={x.support}
                 evidence={x.evidence} sources={x.sources} fit={fit(tags?.objections, i)} index={index} />); }} />
      </section>
    ) : null,
    pricing: <section key="pricing" className="objs price-up"><h3>Pricing</h3>{pricing}</section>,
  };
  const body = sections.map((s) => render[s]).filter(Boolean);

  return (
    <article className="bc2" style={{ "--them": companyColor(report.views.names, them) } as React.CSSProperties}>
      <header className="bc2-head">
        <div>
          <h2>vs {them}</h2>
          {card.overview && <p>{card.overview}</p>}
        </div>
        <div className="bc-tools"><span className="updated">Updated {report.run_date}</span><PrintButton /></div>
      </header>

      <DealBrief report={report} card={card} view={view} deal={deal} />

      {body.length ? body : <p className="empty pad">Not enough evidence yet for this competitor.</p>}

      <p className="hint-line">Click any point to see the source it comes from.</p>

      <details className="more">
        <summary>More detail <span>capabilities · ratings · {pricingUp ? "" : "pricing · "}recent moves · reviewer complaints</span></summary>
        <div className="more-body">
          <Glance us={us} them={them} view={view} />
          {view.rows.length > 0 && (
            <div className="matrix">
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
            {!pricingUp && <div className="cell"><div className="label">Pricing</div>{pricing}</div>}
            <div className="cell">
              <div className="label">Recent moves by {them}</div>
              <ul className="moves">{recent.length ? recent.map((x, i) => (
                <li key={i}>{x.text}<EvidenceBadge ids={x.sources} index={index} /></li>
              )) : <li className="empty">None found this run.</li>}</ul>
              {(report.profiles[them]?.review_weaknesses?.length ?? 0) > 0 && (<>
                <div className="label" style={{ marginTop: 16 }}>{(report.profiles[them]?.ratings?.length ?? 0) > 0
                  ? <>What {them}&apos;s reviewers complain about</>
                  : <>Vulnerabilities</>}</div>
                <ul className="moves">{report.profiles[them]!.review_weaknesses!.map((x, i) => (
                  <li key={i}>{x.text}<EvidenceBadge ids={x.sources} index={index} /></li>))}</ul>
              </>)}
            </div>
            {card.proof_quotes?.length ? (
              <div className="cell">
                <div className="label">Key quotes</div>
                {card.proof_quotes.map((q, i) => <SourceSays key={i} evidence={[{ source: q.source, text: q.quote }]} index={index} />)}
              </div>
            ) : null}
          </div>
          {note && <div className="note"><div className="label">Analyst take</div><p style={{ whiteSpace: "pre-wrap" }}>{note}</p></div>}
        </div>
      </details>
    </article>
  );
}
