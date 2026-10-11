import { notFound } from "next/navigation";
import { Appendix } from "@/components/report/Appendix";
import { BattlecardView } from "@/components/report/Battlecard";
import { AutoPrint } from "@/components/report/ClientBits";
import { Overview } from "@/components/report/Overview";
import { parseDeal } from "@/lib/deal";
import { intel } from "@/lib/intel";
import { indexSources } from "@/lib/report";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

/** The whole report on one page (overview, every battlecard, sources) laid out for paper, which
 *  opens the browser's save-as-PDF dialog on load. Keeps the deal filters it was opened with. */
export async function generateMetadata({ params }: Props) {
  const { id } = await params;
  const { data: r } = await intel.GET("/v1/runs/{run_id}/report", { params: { path: { run_id: id } }, cache: "no-store" });
  return { title: r ? fileName(r.company, r.competitors, r.run_date) : "Battlecards" };
}

/** Browsers suggest the page title as the PDF's file name. */
const fileName = (us: string, them: string[], date: string) => `Battlecards - ${us} vs ${them.join(", ")} - ${date}`;

export default async function PrintReport({ params, searchParams }: Props) {
  const { id } = await params;
  const deal = parseDeal(await searchParams);
  if (!/^[0-9a-f]{10}$/.test(id)) notFound();
  const { data: report } = await intel.GET("/v1/runs/{run_id}/report", { params: { path: { run_id: id } }, cache: "no-store" });
  if (!report) notFound();
  const index = indexSources(report);

  return (
    <main className="print-all">
      <section className="print-page">
        <div className="eyebrow">{report.category || "Market"} · {report.run_date}</div>
        <h1>{report.company} vs {report.competitors.join(", ")}</h1>
        <p className="meta"><b>{report.sources.length}</b> sources, every claim cited</p>
        <Overview report={report} deal={deal} />
      </section>
      {report.battlecards.map((c, i) => (
        <section key={c.competitor} className="print-page">
          <BattlecardView report={report} card={c} view={report.views.cards[i]} index={index} deal={deal} />
        </section>
      ))}
      <section className="print-page"><Appendix report={report} /></section>
      <AutoPrint />
    </main>
  );
}
