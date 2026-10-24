import Lenis from "lenis";
import Snap from "lenis/snap";
import { useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";

/**
 * Smooth scrolling for the scroll-story pages. On desktop, sections marked `[data-snap]` snap
 * into place when you stop near them. Skipped entirely for `prefers-reduced-motion`.
 */
export function useLenis(enabled = true) {
  const reduce = useReducedMotion();
  const lenisRef = useRef<Lenis | null>(null);
  useEffect(() => {
    if (!enabled || reduce) return;
    const lenis = new Lenis({ lerp: 0.1, smoothWheel: true });
    lenisRef.current = lenis;
    let raf = 0;
    const loop = (t: number) => {
      lenis.raf(t);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    let snap: Snap | null = null;
    const desktop = window.matchMedia("(min-width: 1024px)").matches;
    if (desktop) {
      snap = new Snap(lenis, { type: "proximity", duration: 0.9 });
      snap.addElements(Array.from(document.querySelectorAll<HTMLElement>("[data-snap]")), {
        align: ["start"],
      });
    }
    return () => {
      cancelAnimationFrame(raf);
      snap?.destroy();
      lenis.destroy();
      lenisRef.current = null;
    };
  }, [enabled, reduce]);
  return lenisRef;
}
