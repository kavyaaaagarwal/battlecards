import { RunCard } from "@/components/RunCard";
import { RunForm } from "@/components/RunForm";
import { intel } from "@/lib/intel";

export const dynamic = "force-dynamic";

export default async function Home() {
  const { data: featured } = await intel.GET("/v1/runs", { params: { query: { featured: true, limit: 6 } }, cache: "no-store" });
  return (
    <main>
      <section className="hero">
        <div>
          <div className="eyebrow">AI competitive intelligence</div>
          <h1>Sales battlecards an agent researches live - with every claim cited.</h1>
          <p>Name a company and its competitors. The agent searches review sites, forums, news and the vendors&apos; own pages, then writes one-screen battlecards for sales reps.</p>
          <ul>
            <li>Every point links to its source; uncited claims are deleted in code.</li>
            <li>Customer quotes are checked word-for-word and must come from independent sites.</li>
            <li>A vendor&apos;s own blog can&apos;t be the only evidence against a rival.</li>
          </ul>
        </div>
        <RunForm />
      </section>
      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Featured reports</h2>
      <div className="run-cards">
        {(featured ?? []).map((r) => <RunCard key={r.id} run={r} />)}
        {!featured?.length && <p className="empty">No featured reports yet.</p>}
      </div>
    </main>
  );
}
