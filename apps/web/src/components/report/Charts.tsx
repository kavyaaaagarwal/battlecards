import type { Icon as IconName } from "@/lib/deal";

/** Fixed colour per company, by its position in the report (us first): colour follows the
 *  company everywhere, never its rank. Slots are a validated categorical order (see report.css). */
export const companyColor = (names: string[], name: string) => `var(--c${Math.min(names.indexOf(name), 4) + 1})`;

const PATHS: Record<IconName | "win" | "lose", React.ReactNode> = {
  ask: <><circle cx="12" cy="12" r="10" /><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3" /><path d="M12 17h.01" /></>,
  map: <><circle cx="9" cy="7" r="4" /><path d="M2 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2" /><path d="M16 3.1a4 4 0 0 1 0 7.8M22 21v-2a4 4 0 0 0-3-3.9" /></>,
  users: <><circle cx="9" cy="7" r="4" /><path d="M2 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2" /><path d="M16 3.1a4 4 0 0 1 0 7.8M22 21v-2a4 4 0 0 0-3-3.9" /></>,
  target: <><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></>,
  demo: <><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M10 7.5v5l4-2.5z" /><path d="M8 21h8M12 17v4" /></>,
  shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />,
  chat: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
  price: <><path d="M12 1v22" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" /></>,
  doc: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></>,
  clock: <><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>,
  flag: <><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" /><path d="M4 22v-7" /></>,
  win: <path d="M20 6 9 17l-5-5" />,
  lose: <path d="M18 6 6 18M6 6l12 12" />,
};

export function Icon({ name, size = 18 }: { name: keyof typeof PATHS; size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{PATHS[name]}</svg>
  );
}

/** Half-circle gauge for a 0-100 score, with the number and its label in the middle. */
export function Gauge({ value, level, label, name }: { value: number | null; level: string; label: string; name: string }) {
  const r = 52, len = Math.PI * r, v = value ?? 0;
  return (
    <svg className={`gauge g-${level}`} viewBox="0 0 128 76" role="img" aria-label={`${name}: ${label}, ${value ?? "unclear"} of 100`}>
      <path d="M12 66 A52 52 0 0 1 116 66" className="g-track" />
      {value !== null && <path d="M12 66 A52 52 0 0 1 116 66" className="g-fill" strokeDasharray={`${(v / 100) * len} ${len}`} />}
      <text x="64" y="56" className="g-num">{value ?? "?"}</text>
      <text x="64" y="72" className="g-lab">{label}</text>
    </svg>
  );
}

/** Small ring for a single share (e.g. independent sources), value in the middle. */
export function Ring({ pct, label }: { pct: number; label: string }) {
  const r = 22, c = 2 * Math.PI * r;
  return (
    <svg className="ev-ring" viewBox="0 0 56 56" role="img" aria-label={`${label}: ${pct}%`}>
      <circle cx="28" cy="28" r={r} className="r-track" />
      <circle cx="28" cy="28" r={r} className="r-fill" strokeDasharray={`${(pct / 100) * c} ${c}`} transform="rotate(-90 28 28)" />
      <text x="28" y="32" className="r-num">{pct}%</text>
    </svg>
  );
}

/** Part-to-whole donut with a 2px gap between slices; the legend carries names and values. */
export function Donut({ slices, center, sub }: {
  slices: { key: string; value: number; color: string; tip: string }[]; center: string; sub: string;
}) {
  const r = 40, c = 2 * Math.PI * r, total = slices.reduce((s, x) => s + x.value, 0);
  const starts = slices.map((_, i) => slices.slice(0, i).reduce((s, x) => s + (x.value / total) * c, 0));
  return (
    <svg className="donut" viewBox="0 0 100 100" role="img" aria-label={`${sub}: ${slices.map((s) => `${s.key} ${Math.round((100 * s.value) / total)}%`).join(", ")}`}>
      {slices.map((s, i) => {
        const len = (s.value / total) * c, gap = slices.length > 1 ? Math.min(2, len / 2) : 0;
        const el = <circle key={s.key} cx="50" cy="50" r={r} stroke={s.color} className="d-seg" data-tip={s.tip}
                           strokeDasharray={`${len - gap} ${c - len + gap}`} strokeDashoffset={-starts[i]} transform="rotate(-90 50 50)" />;
        return el;
      })}
      <text x="50" y="50" className="d-num">{center}</text>
      <text x="50" y="63" className="d-sub">{sub}</text>
    </svg>
  );
}
