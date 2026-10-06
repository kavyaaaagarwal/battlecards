import { RunCard } from "@/components/RunCard";
import { RunForm } from "@/components/RunForm";
import { intel } from "@/lib/intel";

export const dynamic = "force-dynamic";

export default async function Home() {
  const { data: runs } = await intel.GET("/v1/runs", { params: { query: { limit: 50 } }, cache: "no-store" });
  return (
    <main>
      <section className="hero">
        <div>
          <div className="eyebrow">AI competitive intelligence</div>
          <h1>Skip the research scramble. Walk in with the facts.</h1>
          <p>Enter your company and competitors. The agent researches public sources and builds concise, source-linked battlecards for your sales team.</p>
          <ul>
            <li>Every claim links to its source.</li>
            <li>Customer quotes are checked word for word and drawn from independent sources.</li>
            <li>Competitor claims are checked beyond their own websites.</li>
          </ul>
        </div>
        <RunForm />
      </section>
      <section className="note">
        <h2>A concept, built to grow</h2>
        <p>This version demonstrates the core experience: baseline research and competitor comparisons using public information. It can be tailored with your company data, sales priorities and specific use cases.</p>
        <p>
          Have feedback? <a href="mailto:kavya.agarwal829@gmail.com">Email Kavya</a> or connect on{" "}
          <a href="https://www.linkedin.com/in/copycokavya/" target="_blank" rel="noopener noreferrer">LinkedIn</a>.
        </p>
      </section>
      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Reports</h2>
      <div className="run-cards">
        {(runs ?? []).map((r) => <RunCard key={r.id} run={r} />)}
        {!runs?.length && <p className="empty">No reports yet.</p>}
      </div>
    </main>
  );
}
