import Link from "next/link";

export default function ReportNotFound() {
  return (
    <main>
      <h1>Report not found</h1>
      <p className="meta">This report doesn&apos;t exist, or it was removed. <Link href="/reports">See all reports</Link>.</p>
    </main>
  );
}
