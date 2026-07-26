import { useEffect, useRef, useState } from "react";

/* Before/after detection wipe. Both halves are REAL: the same HERIDAL holdout frame, raw vs.
 * with the shipped fine-tune's detections drawn (native pixels, no synthesis). Draggable
 * divider + keyboard (arrow keys) + an initial scroll-tied sweep so the reveal reads without
 * interaction. */

const BASE = import.meta.env.BASE_URL ?? "/";

export function BeforeAfter() {
  const wrapRef = useRef<HTMLDivElement>(null);
  // starts biased toward the unaided side; the scroll-in sweep opens it to reveal the HADES contacts
  const [pos, setPos] = useState(62);
  const dragging = useRef(false);
  // once the user touches/keys the slider, the auto-sweep may never write pos again: a ref
  // (not a closure flag) so an already-queued rAF tick can't race a pointer interaction
  const interacted = useRef(false);

  // Auto-sweep the divider across as the block scrolls into view, so the reveal reads without any
  // interaction (the behavior the user saw on mobile). It is scroll-driven — it plays only when
  // you scroll it into view — so it runs regardless of prefers-reduced-motion, like the rest of
  // the site's scroll motion. A clear right→left→settle sweep (58 → 30 → 46) shows both halves.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    let raf = 0;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting || interacted.current) return;
        io.disconnect();
        const t0 = performance.now();
        const tick = (t: number) => {
          if (interacted.current) return;
          const k = Math.min(1, (t - t0) / 2600);
          const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2; // easeInOutCubic
          // sweep the divider LEFT to expose the HADES-contacts side (pos 62 → 30), then ease back
          // to a balanced ~48 rest — a clear there-and-back reveal that shows both halves.
          const dip = Math.sin(e * Math.PI); // 0 at start/end, 1 at mid
          const path = 62 - dip * 32 - e * 14; // 62 -> ~16 at mid -> 48 at rest
          setPos(path);
          if (k < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
    };
  }, []);

  const setFromClientX = (clientX: number) => {
    const rect = wrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    setPos(Math.min(96, Math.max(4, ((clientX - rect.left) / rect.width) * 100)));
  };

  return (
    <div
      ref={wrapRef}
      className="ba-wrap"
      onPointerDown={(e) => {
        interacted.current = true;
        dragging.current = true;
        (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
        setFromClientX(e.clientX);
      }}
      onPointerMove={(e) => dragging.current && setFromClientX(e.clientX)}
      onPointerUp={() => (dragging.current = false)}
    >
      {/* base layer = the HADES-detections frame; the unaided frame is clipped ON TOP from the
          LEFT, so the divider wipes: left of the handle = unaided eye, right = HADES contacts */}
      <img src={`${BASE}landing/ba-after.jpg`} alt="Same frame with HADES detections" draggable={false} />
      <div className="ba-top" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}>
        <img src={`${BASE}landing/ba-before.jpg`} alt="Aerial search frame, unaided eye" draggable={false} />
      </div>
      <div
        className="ba-handle"
        style={{ left: `${pos}%` }}
        role="slider"
        aria-label="Reveal detections"
        aria-valuenow={Math.round(pos)}
        aria-valuemin={0}
        aria-valuemax={100}
        tabIndex={0}
        onKeyDown={(e) => {
          interacted.current = true;
          if (e.key === "ArrowLeft") setPos((p) => Math.max(4, p - 4));
          if (e.key === "ArrowRight") setPos((p) => Math.min(96, p + 4));
        }}
      >
        <span className="ba-grip" />
      </div>
      <span className="ba-tag ba-tag-left">Unaided eye</span>
      <span className="ba-tag ba-tag-right">HADES, 5 contacts</span>
    </div>
  );
}
