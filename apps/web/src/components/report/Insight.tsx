import type { CompanyProfile, Excerpt } from "@/lib/types";
import { KIND_LABEL, type SourceIndex, siteOf } from "@/lib/report";
import { EvidenceBadge } from "./Primitives";

/** What the source literally says: a verified verbatim excerpt plus who published it and a link. */
export function SourceSays({ evidence, index }: { evidence?: Excerpt[] | null; index: SourceIndex }) {
  if (!evidence?.length) return null;
  return (
    <div className="says">
      {evidence.map((e, i) => {
        const src = index.get(e.source);
        return (
          <figure className="ex" key={i}>
            <blockquote>“{e.text}”</blockquote>
            {src && (
              <figcaption>
                <a href={src.url} target="_blank" rel="noopener">{siteOf(src)} ↗</a>
                <span className={`kind k-${src.kind}`}>{KIND_LABEL[src.kind] ?? src.kind}</span>
                {src.published && <span>{src.published.slice(0, 10)}</span>}
                <a className="sid" href={`#${src.id}`}>{src.id}</a>
              </figcaption>
            )}
          </figure>
        );
      })}
    </div>
  );
}

/** Published price tiers side by side - numbers straight from each vendor's pricing page. */
export function PricingCompare({ us, them, profiles, index }: {
  us: string; them: string; profiles: Record<string, CompanyProfile>; index: SourceIndex;
}) {
  const col = (name: string) => {
    const p = profiles[name];
    const tiers = p?.pricing_tiers ?? [];
    return (
      <div className="pcol" key={name}>
        <div className={`pname ${name === us ? "us" : "them"}`}>{name}</div>
        {tiers.length ? (
          <table className="tiers"><tbody>{tiers.map((t, i) => (
            <tr key={i}><td>{t.name}</td><td className="price">{t.price}<EvidenceBadge ids={t.sources} index={index} /></td></tr>
          ))}</tbody></table>
        ) : <div className="empty">{p?.pricing_summary?.text ?? "No public pricing found."}</div>}
      </div>
    );
  };
  return <div className="pricing">{col(us)}{col(them)}</div>;
}
