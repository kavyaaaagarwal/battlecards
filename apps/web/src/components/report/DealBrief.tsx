import type { Battlecard, CardView, Report } from "@/lib/types";
import { DEAL_FILTERS, type Deal, focus, isTailored, steps, threat, threatLevel, weights } from "@/lib/deal";
import { splitTldr } from "@/lib/report";
import { Gauge, Icon, Ring } from "./Charts";

const LEVEL = { high: "High", medium: "Medium", low: "Low", unknown: "Unclear" } as const;
const FILTER_ICON = { size: "price", org: "users", stage: "flag", role: "target", motion: "shield" } as const;

/** The deal at a glance, mostly as pictures: how dangerous they are here, where the deal is
 *  decided, how solid the card is, and the three moves to make. Everything below it is detail. */
export function DealBrief({ report, card, view, deal }: { report: Report; card: Battlecard; view: CardView; deal: Deal }) {
  const us = report.company, them = card.competitor;
  const cats = (report.views.categories ?? []).filter((c) => c.scores[us] != null || c.scores[them] != null);
  const w = weights(deal);
  const hot = new Set<string>(focus(deal).map((f) => f.id));
  const rows = [...cats].sort((a, b) => w[b.id] - w[a.id] || Math.abs(view.edges?.[b.id] ?? 0) - Math.abs(view.edges?.[a.id] ?? 0));
  const t = threat(view.edges, deal);
  const level = threatLevel(t);
  const ranked = Object.entries(view.edges ?? {}).filter(([, e]) => e !== null && Math.abs(e!) > 0.1) as [string, number][];
  const label = (id?: string) => cats.find((c) => c.id === id)?.label;
  const ours = label(ranked.filter(([, e]) => e < 0).sort((a, b) => a[1] - b[1])[0]?.[0]);
  const theirs = label(ranked.filter(([, e]) => e > 0).sort((a, b) => b[1] - a[1])[0]?.[0]);
  const moves = steps(deal, them, ours, theirs);
  const [win, lose] = splitTldr(card.tldr);
  const ev = view.evidence;
  const concentrated = !!ev.top_site && ev.items >= 3 && ev.top_site_items * 2 > ev.items;
  const chips = DEAL_FILTERS.filter((f) => deal[f.key]).map((f) => ({
    key: f.key, icon: FILTER_ICON[f.key], text: f.options.find((o) => o.v === deal[f.key])!.l,
  }));

  return (
    <section className="dbrief" aria-label="Deal brief">
      <div className="db-head">
        <h3>Deal brief</h3>
        {isTailored(deal)
          ? <div className="db-chips">{chips.map((c) => <span key={c.key} className="db-chip"><Icon name={c.icon} size={13} />{c.text}</span>)}</div>
          : <span className="db-hint">General brief · set your deal above to tailor it</span>}
      </div>

      <div className="db-grid">
        <div className="db-tile" data-tip="How far ahead of us they are across the categories, weighted for this deal (50 = even)">
          <div className="label">Threat in this deal</div>
          <Gauge value={t} level={level} label={LEVEL[level]} name="Threat in this deal" />
        </div>

        <div className="db-tile db-wide">
          <div className="label">Who&apos;s ahead, by category</div>
          {rows.length ? (
            <div className="dbl" role="table" aria-label={`${us} vs ${them} by category, most important for this deal first`}>
              <div className="dbl-row dbl-h" role="row" aria-hidden="true">
                <span />
                <span className="dbl-sides"><b className="us">← {us} ahead</b><b className="them">{them} ahead →</b></span>
                <span />
              </div>
              {rows.map((c) => {
                const e = view.edges?.[c.id];
                const verdict = e == null ? "No data" : Math.abs(e) <= 0.1 ? "Even"
                  : `${e > 0 ? them : us} ${Math.abs(e) >= 0.5 ? "well ahead" : "ahead"}`;
                const side = e == null ? "none" : Math.abs(e) <= 0.1 ? "even" : e > 0 ? "them" : "us";
                return (
                  <div role="row" key={c.id} className={`dbl-row${hot.has(c.id) ? " hot" : ""}`}
                       data-tip={`${c.label} · ${them}: ${c.detail[them] || "no evidence"} · ${us}: ${c.detail[us] || "no evidence"}`}>
                    <span role="cell" className="dbl-name">{c.label}</span>
                    <span role="cell" className={`dbl-bar ${side}`} aria-hidden="true">
                      {(side === "us" || side === "them") && <i style={{ width: `${Math.min(1, Math.abs(e!)) * 50}%` }} />}
                    </span>
                    <span role="cell" className={`dbl-verdict ${side}`}>{verdict}</span>
                  </div>
                );
              })}
              {isTailored(deal) && hot.size > 0 && <div className="dbl-note">Highlighted: what this buyer weighs most</div>}
            </div>
          ) : <div className="empty">Not enough evidence to compare categories.</div>}
        </div>

        <div className="db-tile">
          <div className="label">Evidence strength</div>
          <div className="db-ring">
            <Ring pct={ev.pct} label="independent sources" />
            <span>{ev.independent} of {ev.total} sources are independent</span>
          </div>
          {concentrated && <div className="concentration" data-tip="If this one page is wrong or biased, most of the card is too.">⚠ {ev.top_site_items} of {ev.items} insights rest on <b>{ev.top_site}</b></div>}
        </div>
      </div>

      <ol className="db-moves" aria-label="Your three moves">
        {moves.map((m, i) => (
          <li key={i}><span className="db-ic"><Icon name={m.icon} /></span><span><b>{i + 1}</b>{m.text}</span></li>
        ))}
      </ol>

      <div className="db-bottom">
        <div className="wl">
          <div className="w"><span><Icon name="win" size={16} /></span>{win}</div>
          {lose && <div className="l"><span><Icon name="lose" size={16} /></span>{lose}</div>}
        </div>
        {card.quick_dismiss && <div className="say-this"><h3>When they come up, say</h3><p>“{card.quick_dismiss}”</p></div>}
      </div>
    </section>
  );
}
