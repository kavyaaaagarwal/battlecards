import type { HistoryPoint } from "@/lib/types";
import { shortDate } from "@/lib/report";

type Props = { us: string; them: string; points: HistoryPoint[] };

/** Review ratings by site across report dates. Each company gets one row per site: faded dots are
 *  earlier reports, the solid dot is this one, joined so the direction of travel reads instantly.
 *  Sites a report didn't find are simply absent - never interpolated. */
export function RatingTrend({ us, them, points }: Props) {
  const latest = points[points.length - 1]?.run_date;
  const sites = [...new Set(points.flatMap((p) => [us, them].flatMap((n) => Object.keys(p.companies[n]?.ratings ?? {}))))];
  if (!sites.length) return <div className="empty">No independent ratings found.</div>;
  const series = (name: string, site: string) => points
    .map((p) => ({ date: p.run_date, r: p.companies[name]?.ratings?.[site] }))
    .filter((x) => x.r);
  const all = sites.flatMap((s) => [us, them].flatMap((n) => series(n, s).map((x) => x.r!.rating5)));
  const lo = Math.max(0, Math.floor((Math.min(...all) - 0.3) * 2) / 2);
  const pct = (v: number) => ((v - lo) / (5 - lo)) * 100;

  return (
    <div className="rt">
      <div className="legend">
        <span><span className="sw dot-us" />{us}</span><span><span className="sw dot-them" />{them}</span>
        {points.length > 1 && <span className="rt-key"><span className="rt-old" /> earlier · <span className="rt-new" /> {shortDate(latest)}</span>}
      </div>
      {sites.map((site) => (
        <div className="rt-site" key={site}>
          <div className="rt-name">{site}</div>
          <div className="rt-lanes">
            {[us, them].map((name) => {
              const xs = series(name, site);
              const who = name === us ? "us" : "them";
              if (!xs.length) return <div className="rt-lane" key={name} />;
              const a = pct(xs[0].r!.rating5), b = pct(xs[xs.length - 1].r!.rating5);
              return (
                <div className="rt-lane" key={name}>
                  {xs.length > 1 && <span className={`rt-line ${who}`} style={{ left: `${Math.min(a, b)}%`, width: `${Math.abs(b - a)}%` }} />}
                  {xs.map((x) => {
                    const r = x.r!, now = x.date === latest;
                    const label = `${r.rating}${r.out_of !== 5 ? `/${r.out_of}` : ""}`;
                    return (
                      <span key={x.date} className={`rt-dot ${who}${now ? "" : " old"}`} style={{ left: `${pct(r.rating5)}%` }}
                            data-tip={`${name} on ${site}, ${shortDate(x.date)}: ${label}${r.review_count ? ` · ${r.review_count.toLocaleString("en-US")} reviews` : ""}`}>
                        {now && <span className={`rt-val${pct(r.rating5) > 85 ? " left" : ""}`}>{label}</span>}
                      </span>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      ))}
      <div className="raxis rt-axis"><span>{lo}</span><span>5</span></div>
    </div>
  );
}
