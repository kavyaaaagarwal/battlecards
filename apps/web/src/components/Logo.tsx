/** The Battlecards mark from the promo film: two overlapping cards, the front one cut out of the back. */
export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 44 44" aria-hidden="true" className="logo">
      <rect x="4" y="8" width="22" height="30" rx="5" fill="#3987e5" transform="rotate(-10 15 23)" />
      <rect x="18" y="6" width="22" height="30" rx="5" fill="#eb6834" stroke="var(--bg)" strokeWidth="3" transform="rotate(8 29 21)" />
    </svg>
  );
}
