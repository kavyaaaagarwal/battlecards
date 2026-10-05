import type { CellView } from "@/lib/types";
import { STATUS_LABEL, type SourceIndex, vendorOf } from "@/lib/report";

type Ids = string[] | string | null | undefined;
const siteOf = (s: { url: string }) => {
  try { return new URL(s.url).hostname.replace(/^www\./, ""); } catch { return s.url; }
};
const list = (ids: Ids, index: SourceIndex) =>
  (typeof ids === "string" ? [ids] : ids ?? []).filter((i) => index.has(i));

export function EvidenceBadge({ ids, index }: { ids: Ids; index: SourceIndex }) {
  const srcs = list(ids, index).map((i) => index.get(i)!);
  if (!srcs.length) return null;
  const sites = [...new Set(srcs.map(siteOf))].join(", ");
  if (srcs.some((s) => !vendorOf(s)))
    return <span className="ev ind" data-tip={`Backed by independent sources: ${sites}`}>Independent</span>;
  const vendor = vendorOf(srcs[0]);
  return <span className="ev ven" data-tip={`Only ${vendor}'s own site says this: ${sites}`}>{vendor}-stated</span>;
}

export function Glyph({ cell }: { cell: CellView }) {
  const label = STATUS_LABEL[cell.status ?? "unknown"];
  const tip = `${cell.company}: ${label}${cell.note ? ` - ${cell.note}` : ""}${
    cell.self ? ` (self-reported: only ${cell.company}'s own site says so)` : ""}`;
  return (
    <>
      <span className={`g g-${cell.status ?? "unknown"}`} role="img"
            aria-label={`${label}${cell.self ? ", self-reported" : ""}`} data-tip={tip} />
      {cell.self && <span className="self" aria-hidden="true">*</span>}
    </>
  );
}

export function GlyphKey() {
  return (
    <div className="glyph-key">
      <span><span className="g g-full" /> Full</span>
      <span><span className="g g-partial" /> Partial / add-on</span>
      <span><span className="g g-none" /> Not offered</span>
      <span><span className="g g-unknown" /> No evidence</span>
      <span><span className="self">*</span> Self-reported (vendor&apos;s own site only)</span>
    </div>
  );
}
