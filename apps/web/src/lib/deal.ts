import type { CardView, CategoryId } from "./types";

/** Deal context a rep sets to re-weight the report. Industry-agnostic on purpose: every B2B deal
 *  has a size, a buyer, a stage and a situation, whatever is being sold. The rules below are plain
 *  sales logic (a CFO weighs price, IT weighs integration and security, a big rollout weighs
 *  implementation risk) - no CRM or internal data needed. */
export type Deal = { size?: string; org?: string; stage?: string; role?: string; motion?: string };
type Opt = { v: string; l: string };
type Filter = { key: keyof Deal; label: string; options: Opt[] };

export const DEAL_FILTERS: Filter[] = [
  { key: "size", label: "Deal size", options: [
    { v: "small", l: "Under $25k / yr" }, { v: "mid", l: "$25k–100k / yr" },
    { v: "large", l: "$100k–500k / yr" }, { v: "strategic", l: "$500k+ / yr" }] },
  { key: "org", label: "Prospect size", options: [
    { v: "smb", l: "Under 200 staff" }, { v: "mid", l: "200–2,000 staff" }, { v: "ent", l: "2,000+ staff" }] },
  { key: "stage", label: "Stage", options: [
    { v: "discovery", l: "Discovery" }, { v: "evaluation", l: "Demo / evaluation" },
    { v: "proposal", l: "Proposal / negotiation" }, { v: "closing", l: "Procurement / close" }] },
  { key: "role", label: "Key buyer", options: [
    { v: "economic", l: "Finance / budget owner" }, { v: "technical", l: "IT / security" },
    { v: "user", l: "Ops / end users" }, { v: "exec", l: "Executive sponsor" }, { v: "procurement", l: "Procurement" }] },
  { key: "motion", label: "Situation", options: [
    { v: "new", l: "Net-new deal" }, { v: "displace", l: "Replacing them" }, { v: "defend", l: "Defending our account" }] },
];

export const CATEGORY_IDS: CategoryId[] = ["product", "pricing", "support", "implementation", "integrations", "rating", "voice"];
type W = Partial<Record<CategoryId, number>>;

/** How much each choice shifts what the buyer weighs. Base weight is 1 per category. */
const BOOST: Record<string, W> = {
  "size:small": { pricing: 1, product: 0.5 },
  "size:large": { implementation: 1, support: 0.5, integrations: 0.5, voice: 0.5 },
  "size:strategic": { implementation: 1, support: 1, integrations: 1, voice: 1, rating: 0.5 },
  "org:smb": { pricing: 1, product: 0.5 },
  "org:mid": { support: 0.5, implementation: 0.5 },
  "org:ent": { integrations: 1, implementation: 0.5, voice: 0.5 },
  "role:economic": { pricing: 2, voice: 0.5 },
  "role:technical": { integrations: 2, implementation: 1 },
  "role:user": { product: 2, support: 1, rating: 0.5 },
  "role:exec": { voice: 1, rating: 0.5, implementation: 0.5 },
  "role:procurement": { pricing: 2, voice: 1 },
  "stage:proposal": { pricing: 1 },
  "stage:closing": { pricing: 0.5, rating: 0.5 },
  "motion:displace": { implementation: 1, support: 0.5 },
  "motion:defend": { pricing: 1, support: 0.5 },
};

const label = (key: keyof Deal, v?: string) =>
  DEAL_FILTERS.find((f) => f.key === key)?.options.find((o) => o.v === v)?.l;

export function parseDeal(q: Record<string, string | string[] | undefined>): Deal {
  const deal: Deal = {};
  for (const f of DEAL_FILTERS) {
    const v = q[f.key];
    if (typeof v === "string" && f.options.some((o) => o.v === v)) deal[f.key] = v;
  }
  return deal;
}

export const isTailored = (d: Deal) => Object.values(d).some(Boolean);

/** Query string carrying the deal (and optional tab), so tab links keep the rep's filters. */
export function dealQuery(d: Deal, extra: Record<string, string> = {}): string {
  const q = new URLSearchParams(extra);
  for (const f of DEAL_FILTERS) if (d[f.key]) q.set(f.key, d[f.key]!); // fixed order: one deal, one URL
  const s = q.toString();
  return s ? `?${s}` : "";
}

export function weights(d: Deal): Record<CategoryId, number> {
  const w = Object.fromEntries(CATEGORY_IDS.map((c) => [c, 1])) as Record<CategoryId, number>;
  for (const [k, v] of Object.entries(d)) {
    if (!v) continue;
    for (const [c, add] of Object.entries(BOOST[`${k}:${v}`] ?? {})) w[c as CategoryId] += add!;
  }
  return w;
}

/** The categories this deal turns on (the top two boosted ones), each with why. */
export function focus(d: Deal): { id: CategoryId; why: string[] }[] {
  const w = weights(d);
  return CATEGORY_IDS.filter((c) => w[c] > 1)
    .sort((a, b) => w[b] - w[a] || CATEGORY_IDS.indexOf(a) - CATEGORY_IDS.indexOf(b))
    .slice(0, 2)
    .map((id) => ({
      id,
      why: DEAL_FILTERS.filter((f) => d[f.key] && BOOST[`${f.key}:${d[f.key]}`]?.[id]).map((f) => label(f.key, d[f.key])!),
    }));
}

/** 0-100: how far ahead of us they are across the categories, weighted for this deal.
 *  50 = even overall. Size counts through the "Market voice" category, not on top of it. */
export function threat(edges: CardView["edges"], d: Deal): number | null {
  const w = weights(d);
  let num = 0, den = 0;
  for (const c of CATEGORY_IDS) {
    const e = edges?.[c];
    if (e === null || e === undefined) continue;
    num += w[c] * e; den += w[c];
  }
  if (!den) return null;
  return Math.round(50 + 50 * (num / den)); // -1 (we're ahead everywhere) .. 1 (they are)
}

export function threatLevel(t: number | null): "high" | "medium" | "low" | "unknown" {
  if (t === null) return "unknown";
  return t >= 58 ? "high" : t >= 46 ? "medium" : "low";
}

/** Indices of a list, deal-relevant points first; ties keep Python's evidence ranking. */
export function rankByDeal(tags: CategoryId[] | undefined, n: number, d: Deal): number[] {
  const w = weights(d);
  const idx = Array.from({ length: n }, (_, i) => i);
  if (!isTailored(d) || !tags?.length) return idx;
  return idx.sort((a, b) => (w[tags[b] ?? "product"] - w[tags[a] ?? "product"]) || a - b);
}

export type Section = "edge" | "asks" | "objections" | "pricing";

/** What a rep needs first at each stage. Pricing only surfaces once money is on the table. */
export function sectionOrder(d: Deal): Section[] {
  switch (d.stage) {
    case "discovery": return ["asks", "edge", "objections"];
    case "proposal": return ["objections", "pricing", "edge", "asks"];
    case "closing": return ["objections", "edge", "asks"];
    default: return ["edge", "asks", "objections"];
  }
}

export type Icon = "ask" | "map" | "target" | "demo" | "shield" | "chat" | "price" | "users" | "doc" | "clock" | "flag";
export type Step = { icon: Icon; text: string };

/** Three moves for this deal: the stage sets the base, the buyer and situation swap in their own.
 *  `ours` / `theirs` are the categories where each side is furthest ahead (labels), if any. */
export function steps(d: Deal, them: string, ours?: string, theirs?: string): Step[] {
  const byStage: Record<string, Step[]> = {
    discovery: [
      { icon: "ask", text: "Ask the trap questions before their demo" },
      { icon: "map", text: "Map who signs, who uses it, who blocks" },
      { icon: "target", text: ours ? `Make ${ours} a must-have criterion` : "Plant one criterion we win on" },
    ],
    evaluation: [
      { icon: "demo", text: ours ? `Steer the evaluation to our lead: ${ours}` : "Demo the workflows they care about" },
      { icon: "shield", text: theirs ? `Pre-empt their edge: ${theirs}` : `Pre-empt ${them}'s strongest pitch` },
      { icon: "users", text: "Put reviewer proof in front of end users" },
    ],
    proposal: [
      { icon: "chat", text: "Handle objections before price comes up" },
      { icon: "price", text: "Frame price against risk and total cost" },
      { icon: "users", text: "Offer a reference from a similar customer" },
    ],
    closing: [
      { icon: "chat", text: "Close out every open objection in writing" },
      { icon: "clock", text: "Show the implementation plan and go-live date" },
      { icon: "users", text: "Line up an exec-to-exec reference call" },
    ],
  };
  const s: Step[] = byStage[d.stage ?? ""] ?? [
    { icon: "target", text: ours ? `Lead with our edge: ${ours}` : "Lead with where we're strongest" },
    { icon: "shield", text: theirs ? `Be ready for their edge: ${theirs}` : `Be ready for ${them}'s strongest pitch` },
    { icon: "ask", text: "Use the questions below to expose their gaps" },
  ];
  const role: Partial<Record<string, Step>> = {
    economic: { icon: "price", text: "Talk total cost and payback, not list price" },
    technical: { icon: "doc", text: "Bring security, integration and API docs" },
    user: { icon: "demo", text: "Let end users try the day-to-day workflow" },
    exec: { icon: "flag", text: "Tie the choice to a business outcome and risk" },
    procurement: { icon: "doc", text: "Have contract terms and vendor-risk answers ready" },
  };
  const motion: Partial<Record<string, Step>> = {
    displace: { icon: "flag", text: `Quantify the cost of staying with ${them}` },
    defend: { icon: "shield", text: "Show the results we've already delivered" },
  };
  const out = [...s];
  if (d.role && role[d.role] && !out.some((x) => x.text === role[d.role!]!.text)) out[1] = role[d.role]!;
  if (d.motion && motion[d.motion]) out[2] = motion[d.motion]!;
  return out;
}

/** Split a ranked list into the points this deal turns on and the rest (shown on request). */
export function splitByDeal(tags: CategoryId[] | undefined, n: number, d: Deal): { top: number[]; rest: number[]; tailored: boolean } {
  const order = rankByDeal(tags, n, d);
  const hot = new Set<string>(focus(d).map((f) => f.id));
  if (!hot.size || !tags?.length) return { top: order.slice(0, 3), rest: order.slice(3), tailored: false };
  const match = order.filter((i) => hot.has(tags[i]));
  if (!match.length) return { top: order.slice(0, 3), rest: order.slice(3), tailored: false };
  const top = match.slice(0, 3);
  return { top, rest: order.filter((i) => !top.includes(i)), tailored: true };
}
