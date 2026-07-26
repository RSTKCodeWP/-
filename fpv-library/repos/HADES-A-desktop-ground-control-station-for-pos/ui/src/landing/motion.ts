import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { useEffect } from "react";

gsap.registerPlugin(ScrollTrigger);

/* This site's scroll animations (reveals, parallax, hero drift, panel grow, smooth scroll) are
 * ALL user-scroll-driven — nothing autoplays, nothing surprises the user with motion they didn't
 * initiate. Per WCAG that class of motion is safe under prefers-reduced-motion (the user controls
 * it by scrolling), and this site's whole experience IS the scroll motion — suppressing it left
 * the page dead for anyone with Reduce Motion on. So the scroll system always runs. Only genuine
 * AUTOPLAY / looping motion (the step-word weight sweep, the CSS load-entrance keyframes) respects
 * the setting — that is what REDUCED now gates, nothing scroll-driven. */
export const REDUCED =
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* the live Lenis instance, so scrollToTop() below can drive Lenis's OWN scroll position (a plain
 * window.scrollTo does not sync with Lenis and gets snapped back). */
let lenisInstance: Lenis | null = null;

/* Jump to the very top instantly. Used on reload and on route change so the new view always starts
 * at the top. Drives Lenis if present (its internal position), and window as a fallback. */
export function scrollToTop() {
  if (lenisInstance) lenisInstance.scrollTo(0, { immediate: true });
  window.scrollTo(0, 0);
}

/* Lenis smooth scroll wired into GSAP's ticker (the canonical pairing): one instance for the
 * whole site. A gentle lerp + a long, soft-tail easing gives the slow-motion, glide-to-rest feel. */
export function useSmoothScroll() {
  useEffect(() => {
    // Never restore the previous scroll position on reload (Cmd+R). We always start at the top,
    // and Lenis manages scroll anyway, so browser scroll restoration only fights us.
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    const lenis = new Lenis({
      // moderate glide (Cubo feel): smoothed + a little inertia, not a heavy 2s luxury glide.
      lerp: 0.1,
      wheelMultiplier: 1,
      easing: (t: number) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t)),
    });
    lenisInstance = lenis;
    lenis.on("scroll", ScrollTrigger.update);
    const raf = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);
    // a fresh load always starts at the top (before the first paint the browser may have jumped)
    scrollToTop();
    return () => {
      gsap.ticker.remove(raf);
      lenis.destroy();
      lenisInstance = null;
    };
  }, []);
}

/* Scroll-linked entrances, the Cubo grammar: each element fades + drifts in from the side it
 * belongs to, SCRUBBED across a scroll range so the motion is tied to scroll position (soft,
 * slow-motion) rather than snapping on a trigger. Transform/opacity only (GPU, 60fps).
 *   data-reveal          -> rise from below (default)
 *   data-reveal="left"   -> from the left
 *   data-reveal="right"  -> from the right
 *   data-reveal="zoom"   -> subtle scale-up settle (large imagery)
 */
/* Cubo's reveal grammar (from teardown): small directional pre-offset, no blur, then settle on
 * a soft ease-out. y40 / x±40 / scale0.9, opacity 0->1, ~0.8s, ease [0.28,0.41,0.56,1]. Calmer
 * and lighter than a big blurred drift; reads as "pieces sliding cohesively into place". */
const CUBO_EASE = "power2.out"; // ~cubic-bezier(0.28,0.41,0.56,1)
const REVEAL_DUR = 0.8;
const FROM: Record<string, gsap.TweenVars> = {
  up: { autoAlpha: 0, y: 40 },
  left: { autoAlpha: 0, x: -40 },
  right: { autoAlpha: 0, x: 40 },
  zoom: { autoAlpha: 0, y: 24, scale: 0.94 },
};
const TO: gsap.TweenVars = { autoAlpha: 1, x: 0, y: 0, scale: 1 };

export function useReveals(deps: unknown[] = []) {
  useEffect(() => {
    const els = gsap.utils.toArray<HTMLElement>("[data-reveal]");
    if (els.length === 0) return;
    const vh = window.innerHeight;
    const tweens = els.map((el) => {
      const dir = el.getAttribute("data-reveal") || "up";
      // index among data-reveal SIBLINGS sharing the same parent, so grouped items (metric
      // grid, card rows, proof points) cascade in rather than popping together.
      const siblings = el.parentElement
        ? Array.from(el.parentElement.children).filter((c) => c.hasAttribute("data-reveal"))
        : [el];
      const idx = Math.max(0, siblings.indexOf(el));
      // anything already in the top ~90% of the viewport on load animates in immediately
      // (a soft entrance), since it will never scroll DOWN through a below-the-fold trigger.
      const aboveFold = el.getBoundingClientRect().top < vh * 0.9;
      if (aboveFold) {
        return gsap.fromTo(el, FROM[dir] ?? FROM.up, {
          ...TO,
          duration: REVEAL_DUR + 0.2,
          ease: CUBO_EASE,
          delay: 0.2 + idx * 0.08,
        });
      }
      // TRIGGER-ONCE with a real time-based duration (NOT scrub): when the element enters view
      // it plays a full fade+drift regardless of scroll speed. Fires once (the Cubo behavior —
      // cohesion comes from continuous parallax, not from re-firing reveals). Per-sibling stagger
      // makes grouped rows cascade in.
      return gsap.fromTo(
        el,
        FROM[dir] ?? FROM.up,
        {
          ...TO,
          duration: REVEAL_DUR,
          ease: CUBO_EASE,
          delay: idx * 0.09,
          scrollTrigger: {
            trigger: el,
            start: "top 86%",
            toggleActions: "play none none none",
            once: true,
          },
        },
      );
    });
    ScrollTrigger.refresh();
    return () => {
      tweens.forEach((t) => {
        t.scrollTrigger?.kill();
        t.kill();
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/* Counter-directional parallax, the Cubo depth trick (their hero: image 0.85x, text 1.05x,
 * a 20% relative drift that is felt rather than seen). Any [data-parallax="0.08"] element
 * drifts +/- that fraction of the viewport as it crosses it, scrubbed to scroll. */
export function useParallax(deps: unknown[] = []) {
  useEffect(() => {
    const els = gsap.utils.toArray<HTMLElement>("[data-parallax]");
    const tweens = els.map((el) => {
      const amount = (parseFloat(el.getAttribute("data-parallax") || "0.08") || 0.08) * window.innerHeight;
      return gsap.fromTo(
        el,
        { y: amount },
        {
          y: -amount,
          ease: "none",
          scrollTrigger: { trigger: el, start: "top bottom", end: "bottom top", scrub: 0.4 },
        },
      );
    });
    return () => {
      tweens.forEach((t) => {
        t.scrollTrigger?.kill();
        t.kill();
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/* Cohesion detail (Cubo): a panel that starts slightly small and grows to full size as it enters
 * the viewport, scrubbed to scroll so it tracks BOTH directions (grows on the way down, shrinks
 * on the way up). Any [data-grow] element scales from 0.92 -> 1 across its entrance. */
export function usePanelGrow(deps: unknown[] = []) {
  useEffect(() => {
    const els = gsap.utils.toArray<HTMLElement>("[data-grow]");
    const tweens = els.map((el) =>
      gsap.fromTo(
        el,
        { scale: 0.92 },
        {
          scale: 1,
          ease: "none",
          transformOrigin: "center bottom",
          scrollTrigger: { trigger: el, start: "top bottom", end: "top center", scrub: 0.5 },
        },
      ),
    );
    return () => {
      tweens.forEach((t) => {
        t.scrollTrigger?.kill();
        t.kill();
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

export { gsap, ScrollTrigger };
