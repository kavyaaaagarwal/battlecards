"use client";
import { useEffect } from "react";

/** One floating tooltip for every [data-tip] element; citation clicks open the Sources list. */
export function TooltipLayer() {
  useEffect(() => {
    const tip = document.getElementById("tip");
    if (!tip) return;
    const over = (e: MouseEvent) => {
      const el = (e.target as Element).closest<HTMLElement>("[data-tip]");
      if (!el) return tip.classList.remove("on");
      tip.textContent = el.dataset.tip ?? "";
      const b = el.getBoundingClientRect();
      tip.style.left = `${Math.min(window.innerWidth - 290, Math.max(8, b.left + b.width / 2 - 60))}px`;
      tip.style.top = `${b.top - 34 < 4 ? b.bottom + 8 : b.top - 34}px`;
      tip.classList.add("on");
    };
    const click = (e: MouseEvent) => {
      if ((e.target as Element).closest(".cite a")) (document.getElementById("sources") as HTMLDetailsElement | null)?.setAttribute("open", "");
    };
    document.addEventListener("mouseover", over);
    document.addEventListener("click", click);
    return () => { document.removeEventListener("mouseover", over); document.removeEventListener("click", click); };
  }, []);
  return <div id="tip" role="tooltip" />;
}

export function PrintButton() {
  return <button className="btn" onClick={() => window.print()}>Print / PDF</button>;
}
