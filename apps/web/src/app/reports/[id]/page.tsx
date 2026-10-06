import Link from "next/link";
import { notFound } from "next/navigation";
import { RunProgress } from "@/components/RunProgress";
import { Appendix } from "@/components/report/Appendix";
import { BattlecardView } from "@/components/report/Battlecard";
import { TooltipLayer } from "@/components/report/ClientBits";
import { Overview } from "@/components/report/Overview";
import { intel } from "@/lib/intel";
import { indexSources, slug } from "@/lib/report";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ tab?: string }> };

export default async function ReportPage({ params, searchParams }: Props) {
  const { id } = await params;
  const { tab } = await searchParams;
  if (!/^[0-9a-f]{10}$/.test(id)) notFound();

  const { data: status } = await intel.GET("/v1/runs/{run_id}", { params: { path: { run_id: id } }, cache: "no-store" });
  if (!status) notFound();
  if (status.status !== "succeeded" && status.status !== "partial") return <RunProgress runId={id} initial={status} />;

  const { data: report } = await intel.GET("/v1/runs/{run_id}/report", { params: { path: { run_id: id } }, cache: "no-store" });
  if (!report) notFound();

  const index = indexSources(report);
  const active = report.battlecards.findIndex((c) => slug(c.competitor) === tab);
  const dropped = (report.stats?.claims_dropped ?? 0) + (report.stats?.quotes_dropped ?? 0);

  return (
    <main>
      <div className="eyebrow">{report.category || "Market"} · {report.run_date}</div>
      <h1>{report.company} vs {report.competitors.join(", ")}</h1>
      <p className="meta">
        <b>{report.sources.length}</b> sources · every claim cited · <b>{dropped}</b> uncited claims or unverifiable quotes removed automatically
        {" · "}<a href={`/api/runs/${id}/export`}>Download Markdown</a>
      </p>
      {report.status === "partial" && <p className="hint">Some research stages didn&apos;t finish, so parts of this report may be missing.</p>}
      {report.degraded && <p className="hint">This run used fallback search, so it has fewer review sources.</p>}

      <nav className="tabs">
        <Link href={`/reports/${id}`} className="tab" aria-current={active < 0 ? "page" : undefined}>Overview</Link>
        {report.battlecards.map((c, i) => (
          <Link key={c.competitor} href={`/reports/${id}?tab=${slug(c.competitor)}`} className="tab" aria-current={i === active ? "page" : undefined}>
            vs {c.competitor}
          </Link>
        ))}
      </nav>

      {active < 0
        ? <Overview report={report} />
        : <BattlecardView report={report} card={report.battlecards[active]} view={report.views.cards[active]} index={index} />}

      <Appendix report={report} />
      <TooltipLayer />
    </main>
  );
}
