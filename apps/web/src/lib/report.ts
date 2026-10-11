import type { Rating, Report, SourceOut } from "./types";

export type SourceIndex = Map<string, SourceOut>;

export const indexSources = (r: Report): SourceIndex => new Map(r.sources.map((s) => [s.id, s]));

export const vendorOf = (s: Pick<SourceOut, "origin">): string | null =>
  s.origin?.startsWith("vendor:") ? s.origin.slice(7) : null;

export const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

/** Position of a rating on a lo..5 axis, in percent (ratings out of 10 are normalised). */
export function ratingPct(r: Pick<Rating, "rating" | "out_of"> | null | undefined, lo: number): number {
  if (!r || lo >= 5) return 0;
  const v = (r.rating / (r.out_of ?? 5)) * 5;
  return Math.max(0, Math.min(100, ((v - lo) / (5 - lo)) * 100));
}

export function ratingText(r: Rating): string {
  const scale = (r.out_of ?? 5) !== 5 ? `/${r.out_of}` : "";
  const count = r.review_count ? ` · ${r.review_count.toLocaleString("en-US")} reviews` : "";
  return `${r.rating}${scale}${count}`;
}

export const STATUS_LABEL = { full: "Full", partial: "Partial", none: "Not offered", unknown: "Unknown" } as const;
export const VERDICT_LABEL = { lead: "▲ We lead", behind: "▼ They lead", even: "= Even", unknown: "? Unclear" } as const;

export const KIND_LABEL = {
  review: "Review site", community: "Forum", news: "News", reference: "Reference",
  analysis: "Third-party article", vendor: "Vendor site",
} as const;

/** How well a claim is backed - the rule lives in Python (domain/support.py); this is just the wording. */
export const SUPPORT_LABEL = {
  corroborated: { label: "Corroborated", tip: "Verbatim evidence from 2+ independent sites" },
  single_source: { label: "1 independent source", tip: "Verbatim evidence from one independent site - fine to use, worth a second source" },
  vendor_claim: { label: "Vendor's claim", tip: "Only the company's own pages say this - present it as their claim, not a fact" },
  cited_only: { label: "Check source", tip: "Cited, but no exact excerpt could be verified on the page - read the source before using" },
} as const;

export const siteOf = (s: { url: string }) => {
  try { return new URL(s.url).hostname.replace(/^www\./, ""); } catch { return s.url; }
};

/** "We win when X. We lose when Y." -> the two halves, so each gets its own line. */
export function splitTldr(tldr: string): [string, string | null] {
  const m = tldr.match(/^(.*?)\s*(We (?:usually )?lose when.*)$/i);
  return m ? [m[1], m[2]] : [tldr, null];
}

export const shortDate = (d: string) =>
  new Date(`${d}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
