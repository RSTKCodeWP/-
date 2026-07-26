import type { LngLat } from "./geo";

/* Eased pin-motion primitives (DESIGN-SYSTEM §4.5: glide, never teleport). The MapView
 * keeps a PinTweener per displayed track; when a track's coordinate refines, it starts a
 * ~400ms ease-out glide from the old to the new position. A new fix arriving mid-glide
 * RETARGETS from the current interpolated point (never queues/stacks). */

export function easeOutCubic(t: number): number {
  const u = 1 - t;
  return 1 - u * u * u;
}

export function lerpLngLat(a: LngLat, b: LngLat, t: number): LngLat {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

interface Glide {
  from: LngLat;
  to: LngLat;
  startMs: number;
}

/** Tracks eased positions for many pins keyed by track_id. Time is injected (testable). */
export class PinTweener {
  private readonly glides = new Map<number, Glide>();
  private readonly current = new Map<number, LngLat>();

  constructor(private readonly durationMs = 400) {}

  /** Report a track's latest target. Starts/retargets a glide if the position changed. */
  setTarget(trackId: number, target: LngLat, nowMs: number): void {
    const cur = this.current.get(trackId);
    if (!cur) {
      // first sighting — appear in place, no glide
      this.current.set(trackId, target);
      return;
    }
    if (cur[0] === target[0] && cur[1] === target[1]) return; // unchanged
    // retarget from the CURRENT interpolated point (never teleport, never stack)
    this.glides.set(trackId, { from: cur, to: target, startMs: nowMs });
  }

  /** Advance all glides to nowMs; returns the eased position for a track. */
  positionAt(trackId: number, nowMs: number): LngLat | undefined {
    const glide = this.glides.get(trackId);
    if (glide) {
      const t = Math.min(1, (nowMs - glide.startMs) / this.durationMs);
      const pos = lerpLngLat(glide.from, glide.to, easeOutCubic(t));
      this.current.set(trackId, pos);
      if (t >= 1) this.glides.delete(trackId);
      return pos;
    }
    return this.current.get(trackId);
  }

  /** True while any pin is still gliding (the MapView keeps ticking until then). */
  get active(): boolean {
    return this.glides.size > 0;
  }

  forget(trackId: number): void {
    this.glides.delete(trackId);
    this.current.delete(trackId);
  }
}
