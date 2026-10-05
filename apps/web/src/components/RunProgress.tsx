"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { RunStatus } from "@/lib/types";

const STAGES: [string, string][] = [
  ["collect", "Collecting sources"], ["profiles", "Profiling companies"], ["battlecards", "Writing battlecards"],
  ["matrix", "Building the capability matrix"], ["positioning", "Analysing positioning"], ["finalize", "Finishing up"],
];
const STALL_MS = 10 * 60 * 1000; // a stage never runs longer than ~4 minutes
const ICON: Record<string, string> = { done: "✓", running: "…", retrying: "↻", skipped: "–", failed: "✕", waiting: "·" };

export function RunProgress({ runId, initial }: { runId: string; initial: RunStatus }) {
  const router = useRouter();
  const [status, setStatus] = useState(initial);
  const [tick, setTick] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (status.status === "succeeded" || status.status === "partial") { router.refresh(); return; }
    if (status.status === "failed") return;
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`/api/runs/${runId}`, { cache: "no-store" });
        if (res.ok) setStatus(await res.json());
      } finally { setTick((n) => n + 1); setNow(Date.now()); }
    }, 3000);
    return () => clearTimeout(t);
  }, [status, tick, runId, router]);

  const byStage = new Map(status.progress.map((p) => [p.stage, p]));
  const lastActivity = Math.max(...[status.created_at, ...status.progress.map((p) => p.at)].map((t) => Date.parse(t) || 0));
  const stalled = (status.status === "running" || status.status === "queued") && now - lastActivity > STALL_MS;
  return (
    <main>
      <div className="eyebrow">Research run · {runId}</div>
      <h1>{status.company} vs {status.competitors.join(", ")}</h1>
      <p className="meta">{status.status === "failed" ? "This run stopped." : "The agent is researching. This page updates by itself - usually 3-5 minutes."}</p>
      <ul className="box progress">
        {STAGES.map(([key, label]) => {
          const p = byStage.get(key);
          const state = p?.status ?? "waiting";
          return (
            <li key={key} className={state}>
              <span className="pi" aria-hidden="true">{ICON[state]}</span>
              <span><b>{label}</b>{p?.note && <span className="pn">{p.note}</span>}</span>
            </li>
          );
        })}
      </ul>
      {status.degraded && <p className="hint">Today&apos;s search budget is used up, so this run uses fallback search with fewer review sources.</p>}
      {stalled && (
        <div className="box" role="alert" style={{ marginTop: 14 }}>
          <b>This run looks stuck</b> - nothing has happened for over 10 minutes.
          <div style={{ marginTop: 8 }}><Link href="/">Start it again</Link> with the same names; it picks up where it stopped.</div>
        </div>
      )}
      {status.status === "failed" && (
        <div className="box" role="alert" style={{ marginTop: 14 }}>
          <b>Couldn&apos;t finish this report.</b> {status.error}
          <div style={{ marginTop: 8 }}><Link href="/">Try again</Link> - free AI models are sometimes busy.</div>
        </div>
      )}
    </main>
  );
}
