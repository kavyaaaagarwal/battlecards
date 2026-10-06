import { RunCard } from "@/components/RunCard";
import { intel } from "@/lib/intel";

export const dynamic = "force-dynamic";

export default async function Reports() {
  const { data: runs } = await intel.GET("/v1/runs", { params: { query: { limit: 50 } }, cache: "no-store" });
  return (
    <main>
      <div className="eyebrow">Reports</div>
      <h1>All reports</h1>
      <p className="meta">Finished research runs, newest first.</p>
      <div className="run-cards" style={{ marginTop: 20 }}>
        {(runs ?? []).map((r) => <RunCard key={r.id} run={r} />)}
        {!runs?.length && <p className="empty">No reports yet.</p>}
      </div>
    </main>
  );
}
