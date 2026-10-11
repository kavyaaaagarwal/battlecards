"use client";

import { useEffect, useRef, useState } from "react";

const W = 1280;
const H = 792; // 720 film + 72 player controls

/** The promo film (a 1280×792 HTML export in public/promo) scaled to fit its column; it has its own player controls. */
export function PromoFrame() {
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setScale(e.contentRect.width / W));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={box} className="promo" style={{ aspectRatio: `${W} / ${H}` }}>
      {scale > 0 && (
        <iframe
          src="/promo/film.dc.html"
          title="Every deal is different: Battlecards in one minute"
          allow="autoplay"
          width={W}
          height={H}
          style={{ transform: `scale(${scale})` }}
        />
      )}
    </div>
  );
}
