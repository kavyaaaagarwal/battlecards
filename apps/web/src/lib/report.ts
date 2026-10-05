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
