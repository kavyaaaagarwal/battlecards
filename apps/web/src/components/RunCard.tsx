import Link from "next/link";
import type { RunSummary } from "@/lib/types";

export function RunCard({ run }: { run: RunSummary }) {
  return (
    <Link href={`/reports/${run.id}`} className="run-card">
      <div className="eyebrow">{run.category || "Market"} · {run.run_date}</div>
      <b>{run.company}</b>
      <div className="vs">vs {run.competitors.join(", ")}</div>
    </Link>
  );
}
