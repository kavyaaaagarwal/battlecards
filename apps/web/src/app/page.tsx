import Link from "next/link";
import { PromoFrame } from "@/components/PromoFrame";
import { RunCard } from "@/components/RunCard";
import { BetaAccess } from "@/components/BetaAccess";
import { RunForm } from "@/components/RunForm";
import { Icon } from "@/components/report/Charts";
import { TooltipLayer } from "@/components/report/ClientBits";
import { DealBrief } from "@/components/report/DealBrief";
import { type Deal, dealQuery } from "@/lib/deal";
import { intel } from "@/lib/intel";
import { slug } from "@/lib/report";

export const dynamic = "force-dynamic";

/** The deal the "what your rep sees" example is tailored to. */
const SAMPLE_DEAL: Deal = { size: "large", stage: "proposal", role: "economic" };

function Frame({ url, children }: { url: string; children: React.ReactNode }) {
  return (
    <div className="frame">
      <div className="frame-bar" aria-hidden="true"><i /><i /><i /><span>{url}</span></div>
      <div className="frame-body">{children}</div>
    </div>
  );
}

export default async function Home() {
  const [{ data: runs }, { data: features }] = await Promise.all([
    intel.GET("/v1/runs", { params: { query: { limit: 12 } }, cache: "no-store" }),
    intel.GET("/v1/features", { cache: "no-store" }),
  ]);
  const canRun = !!features?.runs_enabled; // ALLOW_RUNS: staging and local research live, production collects requests
  const latest = runs?.find((r) => r.status === "succeeded");
  const { data: report } = latest
    ? await intel.GET("/v1/runs/{run_id}/report", { params: { path: { run_id: latest.id } }, cache: "no-store" })
    : { data: undefined };

  const sample = report && report.battlecards.length ? report : null;
  const href = sample ? `/reports/${sample.id}` : "/reports";
  const card = sample?.battlecards[0];
  const independent = sample?.sources.filter((s) => s.kind !== "vendor").length ?? 0;
  const voice = sample?.views.categories?.find((c) => c.id === "voice")?.values ?? {};
  const reviews = Object.values(voice).reduce<number>((t, n) => t + (n ?? 0), 0);

  return (
    <main className="lp">
      <section className="lp-hero">
        <div className="lp-hero-text">
          <div className="eyebrow">Competitive intelligence for B2B SaaS sales</div>
          <h1>A battlecard for every deal, not just every competitor.</h1>
          <p className="lp-sub">
            Name your rivals. An AI agent reads their reviews, forums, news and pricing pages and builds cited
            battlecards in minutes. Tell it the deal&apos;s size, stage and buyer, and the card rebuilds around it.
          </p>
          <div className="lp-cta">
            <Link href={href} className="btn primary">See a live report</Link>
            <a href="#try" className="btn">{canRun ? "Run it on your market" : "Register interest"}</a>
          </div>
          <ul className="lp-ticks">
            <li>Every claim linked to its source</li>
            <li>Re-run any time to see what changed</li>
            <li>Works in any B2B category</li>
          </ul>
        </div>
        <figure className="lp-film">
          <PromoFrame />
          <figcaption>One minute · turn the sound on · subtitles with CC</figcaption>
        </figure>
      </section>

      {sample && (
        <section className="lp-shot" aria-label="Live sample report">
          <div className="lp-cap">From the live sample · <b>{sample.company}</b> vs {sample.competitors.join(", ")} · {sample.category || "B2B software"}</div>
          <dl className="lp-proof">
            <div><dt>{sample.sources.length}</dt><dd>pages read and cited</dd></div>
            <div><dt>{Math.round((100 * independent) / sample.sources.length)}%</dt><dd>independent: reviews, forums, news, analysts</dd></div>
            <div><dt>{(sample.views.categories ?? []).length}</dt><dd>buying categories scored per competitor</dd></div>
            {reviews > 0 && <div><dt>{reviews.toLocaleString("en-US")}</dt><dd>customer reviews behind the ratings</dd></div>}
          </dl>
        </section>
      )}

      <section className="lp-why">
        <h2>Built for how competitive deals are actually lost</h2>
        <div className="lp-why-grid">
          <article>
            <span className="lp-ic"><Icon name="clock" /></span>
            <h3>Battlecards go stale in a quarter</h3>
            <p>Re-run any time. Each report shows what moved since the last one: price changes, rating shifts, launches, and what reps should do about them.</p>
          </article>
          <article>
            <span className="lp-ic"><Icon name="shield" /></span>
            <h3>Reps don&apos;t use what they can&apos;t trust</h3>
            <p>Every claim links to its source. Customer quotes are checked word for word, and a vendor&apos;s own site never counts as proof against a rival.</p>
          </article>
          <article>
            <span className="lp-ic"><Icon name="target" /></span>
            <h3>One card doesn&apos;t fit every deal</h3>
            <p>Set deal size, stage and buyer. The card reorders itself: a CFO in negotiation gets pricing and objections first, IT gets integration and security.</p>
          </article>
        </div>
      </section>

      {sample && card && (
        <section className="lp-rep">
          <div className="lp-rep-h">
            <div>
              <h2>What your rep sees before the call</h2>
              <p>{sample.company} vs {card.competitor}, tailored to a $100k–500k deal in negotiation with a finance buyer.</p>
            </div>
            <Link href={`${href}${dealQuery(SAMPLE_DEAL, { tab: slug(card.competitor) })}`} className="lp-link">Open the full battlecard →</Link>
          </div>
          <Frame url={`battlecards / ${sample.company.toLowerCase()} / vs ${card.competitor.toLowerCase()}`}>
            <div className="lp-brief">
              <DealBrief report={sample} card={card} view={sample.views.cards[0]} deal={SAMPLE_DEAL} />
            </div>
          </Frame>
        </section>
      )}

      {canRun ? (
        <section className="lp-try" id="try">
          <div className="lp-steps">
            <h2>Try it on your own market</h2>
            <p>Works for any B2B category: HR tech, fintech, dev tools, CRM, support software.</p>
            <ol>
              <li><b>Name your company and up to four competitors.</b> Add the category if names are ambiguous.</li>
              <li><b>The agent does the research.</b> Review sites, forums, news, pricing pages and independent comparisons, with quality rules enforced in code.</li>
              <li><b>Your team gets the report.</b> An overview of who leads where, and one battlecard per competitor that tailors itself to each deal.</li>
            </ol>
          </div>
          <RunForm />
        </section>
      ) : <BetaAccess runs={runs ?? []} />}

      {canRun && !!runs?.length && (
        <section className="lp-recent">
          <div className="ov-h"><h3>Recent reports</h3><Link href="/reports">All reports →</Link></div>
          <div className="run-cards">{runs.slice(0, 3).map((r) => <RunCard key={r.id} run={r} />)}</div>
        </section>
      )}
      <TooltipLayer />
    </main>
  );
}
