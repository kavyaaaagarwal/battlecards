import type { Report } from "@/lib/types";
import { ratingText } from "@/lib/report";

/** One compact card per company for the report header: who they are, key facts, ratings, pricing. */
export function Snapshots({ report }: { report: Report }) {
  const v = report.views;
  return (
    <div className="snaps">
      {v.names.map((name) => {
        const p = report.profiles[name];
        const f = report.facts?.[name] ?? {};
        const ratings = v.market_ratings.find((r) => r.name === name)?.by_site ?? {};
        const tiers = p?.pricing_tiers ?? [];
        const facts = [f.founded && `Founded ${f.founded}`, f.headquarters, f.employees && `${f.employees} staff`, f.owner && `Owned by ${f.owner}`]
          .filter(Boolean).join(" · ");
        return (
          <div className={`snap${name === report.company ? " is-us" : ""}`} key={name}>
            <div className="snap-h">
              <h3>{name}</h3>
              {name === report.company && <span className="us-tag">YOU</span>}
              {p?.domain && <a href={`https://${p.domain}`} target="_blank" rel="noopener">{p.domain} ↗</a>}
            </div>
            {p?.positioning && <p className="snap-pos" title={p.positioning.text}>{p.positioning.text}</p>}
            {facts && <div className="snap-facts">{facts}</div>}
            <div className="snap-chips">
              {v.sites.map((s) => ratings[s] && (
                <span className="chip" key={s} data-tip={`${name} on ${s}: ${ratingText(ratings[s])}`}>
                  {s.replace(" Peer Insights", "")} <b>{ratings[s].rating}{(ratings[s].out_of ?? 5) !== 5 ? `/${ratings[s].out_of}` : ""}</b>
                </span>
              ))}
              <span className="chip muted">{tiers.length ? `${tiers.length} public price tier${tiers.length > 1 ? "s" : ""}` : "No public pricing"}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
