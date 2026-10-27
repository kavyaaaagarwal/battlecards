import Link from "next/link";
import { RequestForm } from "@/components/RequestForm";
import type { RunSummary } from "@/lib/types";

/** Production: access is invite-only, so the visitor registers interest, and meanwhile is sent to
 *  the real reports to see what they'd get. One report per company and market, newest first: a
 *  company researched in two markets is two different reports, so both are worth showing. */
export function BetaAccess({ runs }: { runs: RunSummary[] }) {
  const key = (r: RunSummary) => `${r.company}\u0000${r.category}`;
  const reports = runs.filter((r, i) => runs.findIndex((x) => key(x) === key(r)) === i).slice(0, 5);
  return (
    <section className="lp-try lp-beta" id="try">
      <div className="beta-left">
        <span className="beta-badge">Beta · invite-only</span>
        <h2>Battlecards is in beta</h2>
        <p className="beta-sub">
          Access is invite-only while we&apos;re in beta. Register your interest and we&apos;ll give you access once
          we&apos;ve reviewed your request.
        </p>

        {reports.length > 0 && (
          <div className="beta-reports">
            <div className="beta-reports-h">
              <h3>Explore live reports while you wait</h3>
              <p>Real reports the agent produced. Open one, pick a competitor tab, then set a deal at the top and watch the battlecard rebuild.</p>
            </div>
            <ul>
              {reports.map((r) => (
                <li key={r.id}>
                  <Link href={`/reports/${r.id}`}>
                    <span className="beta-co">{r.company.slice(0, 1)}</span>
                    <span className="beta-txt">
                      <b>{r.company} <span>vs {r.competitors.join(", ")}</span></b>
                      <small>{r.category || "Market"} · {r.run_date}</small>
                    </span>
                    <span className="beta-go" aria-hidden="true">→</span>
                  </Link>
                </li>
              ))}
            </ul>
            <Link href="/reports" className="lp-link">Browse all reports →</Link>
          </div>
        )}
      </div>
      <RequestForm />
    </section>
  );
}
