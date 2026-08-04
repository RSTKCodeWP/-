/**
 * Shared 3D waypoint symbology — the conformal "highway in the sky" the pilot
 * likes from the Sim World, extracted so it can be reused by ANY three.js scene:
 * the in-app simulator world (sim-world-scene) AND the HUD's world-locked overlay
 * (HudWorldOverlay) that paints over synthetic vision (and, later, live video).
 *
 * Two looks share one implementation, selected by `options.compact`:
 *  - Perspective (default, the Sim World): billboard reticles + captions that
 *    grow with proximity (sizeAttenuation on), a core sphere + drop line per
 *    waypoint, a caption on every waypoint. Reads great from a chase camera.
 *  - Compact HUD (HudWorldOverlay): the same world-locked positions, but the
 *    reticles + labels are CONSTANT SCREEN SIZE (sizeAttenuation OFF) so a
 *    waypoint 20 m away does not fill the frame; captions show for only the
 *    active + next waypoint; no core spheres / drop lines; dimmer, thin route
 *    line. This is the augment-don't-cover look for a close-up first-person HUD.
 *
 * Coordinate frame — every position is NED metres [north, east, down] from the
 * scene origin (home in the sim world; the HUD's local origin in the overlay).
 * We map to three.js Y-up exactly as the sim world and the SVT scene do:
 *   three.x =  East  =  position[1]
 *   three.y =  Up    = -position[2]
 *   three.z = -North = -position[0]
 * so a caller that also positions its camera with this mapping gets waypoints
 * that land on the terrain with no per-scene calibration.
 */

import * as THREE from 'three';

/** A mission waypoint in local NED metres from the scene origin. */
export interface Wp {
  seq: number;
  /** NED metres [north, east, down] from the scene origin. */
  position: [number, number, number];
  /** The active / next waypoint — drawn with a brighter, larger reticle. When
      omitted, `activeSeq` passed to update() decides emphasis instead. */
  active?: boolean;
}

export interface WaypointSymbologyOptions {
  /**
   * Compact HUD mode: constant screen-size reticles (never balloon up close),
   * at most two captions (active + next), no core spheres / drop lines, dimmer
   * and a thin route line. Omit / false for the perspective Sim-World look.
   */
  compact?: boolean;
}

export interface WaypointSymbology {
  /** Add this to your scene. Holds every waypoint's persistent sprites/lines. */
  group: THREE.Group;
  /**
   * Rebuild the symbology when the mission (or active waypoint) changes, then
   * refresh each caption's live slant-range from `flownPos` (the flown vehicle's
   * three-space position, or the camera position as a fallback). `activeSeq`
   * flags the next waypoint for emphasis (or null / -1 for none).
   */
  update(waypoints: Wp[], flownPos: THREE.Vector3, activeSeq: number | null): void;
  /** Show / hide the whole group. */
  setVisible(on: boolean): void;
  dispose(): void;
}

/** Visual scale (metres) shared with the sim world so both look identical. */
const SYMBOL_SCALE = 2.2;
/** Cyan used across the (inactive) waypoint markers. */
const WP_CYAN = '#22d3ee';
/** Amber used to emphasise the active / next waypoint. */
const WP_ACTIVE = '#fbbf24';
/** Active reticle is drawn larger than the rest (a clear "fly here" cue). */
const ACTIVE_BOOST = 1.35;

// ─── Compact HUD-mode sizing ─────────────────────────────────────────────────
// With sizeAttenuation OFF a sprite's scale is a fraction of the viewport HEIGHT
// (scale 1 ≈ full height), so these read as a roughly constant pixel size across
// panel sizes. On a ~700 px tall panel: reticle ≈ 35 px, active ≈ 46 px.
const COMPACT_RETICLE = 0.062;
const COMPACT_LABEL_H = 0.075;
const COMPACT_LABEL_W = 0.15;
/** Small number-only tag shown ABOVE every non-active compact waypoint so the
    pilot can read them all (like the map) without a full caption on each. */
const COMPACT_NUM_H = 0.05;
const COMPACT_NUM_W = 0.1;
/** Far reticles shrink toward this (never grow past the near size) for depth.
    Kept close to 1 so distant waypoints stay legible rather than vanishing. */
const COMPACT_MIN_SHRINK = 0.82;

// ─── Caption budget ──────────────────────────────────────────────────────────
// Captions are canvas-backed sprites whose text carries a LIVE slant range, so
// each refresh is a 2D redraw plus a GPU texture upload. A caption per waypoint
// does not survive contact with a generated survey: a 573-waypoint TOPAS mission
// held 573 canvases (~75 MB of texture) and redrew every one of them on every
// frame, because the rounded metre value changes constantly while flying. That
// is what pinned the Sim World at 1 fps.
//
// Instead a fixed POOL of caption sprites is reassigned to the waypoints that
// currently matter, so cost is bounded by pool size, never by mission length.
/**
 * Live captions in the perspective (Sim World) look.
 *
 * Captions are what make the highway READ: an 8.8-unit sprite with a filled
 * background and bright text, against reticles that are thin brackets and cores
 * about a metre across. Budget too few and a survey route goes from a legible wall
 * of labels to a faint scattering of outlines, so this is deliberately generous -
 * 48 canvases is ~6 MB of texture and at most 48 redraws per refresh, still two
 * orders of magnitude below the per-waypoint-per-frame version it replaced.
 */
const CAPTION_POOL_PERSPECTIVE = 48;
/** Live captions in the compact HUD: the active + next waypoint, as before. */
const CAPTION_POOL_COMPACT = 2;
/** Above this many waypoints the compact HUD drops its per-waypoint number tags.
    The reticles and route line still carry the whole route; a number tag per
    waypoint is unreadable at survey density anyway, and each one costs a texture.
    Mirrors the flight map's SEMANTIC_MARKER_THRESHOLD reasoning. */
const NUMBER_TAG_BUDGET = 120;
/** Captions refresh at 5 Hz rather than per frame. Slant range in whole metres
    does not need 60 Hz, and every refresh is a canvas redraw + texture upload. */
const CAPTION_REFRESH_MS = 200;

/** three.x = East, three.y = Up, three.z = -North (NED [n,e,d] -> three). */
function nedToThree(pos: [number, number, number], out: THREE.Vector3): THREE.Vector3 {
  return out.set(pos[1], -pos[2], -pos[0]);
}

/** Draw a HUD-style target reticle (corner brackets + centre dot) in `color`.
    A dark halo is laid under the bright strokes so the reticle stays readable
    on any background: green synthetic terrain, bright sky, or a live feed. */
function drawReticle(canvas: HTMLCanvasElement, texture: THREE.CanvasTexture, color: string): void {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const s = canvas.width;
  ctx.clearRect(0, 0, s, s);
  ctx.lineCap = 'round';
  const m = 20; // margin from the edge
  const arm = 36; // bracket arm length
  const corners: Array<[number, number, number, number]> = [
    [m, m, 1, 1],
    [s - m, m, -1, 1],
    [m, s - m, 1, -1],
    [s - m, s - m, -1, -1],
  ];
  const strokeBrackets = (style: string, width: number): void => {
    ctx.strokeStyle = style;
    ctx.lineWidth = width;
    for (const [x, y, dx, dy] of corners) {
      ctx.beginPath();
      ctx.moveTo(x + dx * arm, y);
      ctx.lineTo(x, y);
      ctx.lineTo(x, y + dy * arm);
      ctx.stroke();
    }
  };
  strokeBrackets('rgba(0,0,0,0.6)', 13); // contrast halo
  strokeBrackets(color, 6);
  // Centre dot, also haloed.
  ctx.beginPath();
  ctx.arc(s / 2, s / 2, 9, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(0,0,0,0.6)';
  ctx.fill();
  ctx.beginPath();
  ctx.arc(s / 2, s / 2, 6, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  texture.needsUpdate = true;
}

/** Draw a small number-only tag ("12") with a dark halo, for the compact HUD's
    non-active waypoints so every one is legible without a full caption. */
function drawWpNumber(canvas: HTMLCanvasElement, texture: THREE.CanvasTexture, text: string, accent: string): void {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = 'bold 48px ui-monospace, SFMono-Regular, Menlo, monospace';
  ctx.lineJoin = 'round';
  ctx.lineWidth = 9;
  ctx.strokeStyle = 'rgba(0,0,0,0.72)';
  ctx.strokeText(text, canvas.width / 2, canvas.height / 2);
  ctx.fillStyle = accent;
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);
  texture.needsUpdate = true;
}

/** Draw a two-line waypoint caption ("WP 4" / "120m · 45m") in `accent`. */
function drawWpLabel(
  canvas: HTMLCanvasElement,
  texture: THREE.CanvasTexture,
  line1: string,
  line2: string,
  accent: string,
): void {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = 'bold 40px ui-monospace, SFMono-Regular, Menlo, monospace';
  const w1 = ctx.measureText(line1).width;
  ctx.font = '32px ui-monospace, SFMono-Regular, Menlo, monospace';
  const w2 = ctx.measureText(line2).width;
  const padX = 24;
  const w = Math.min(canvas.width, Math.max(w1, w2) + padX * 2);
  const h = 88;
  const x = (canvas.width - w) / 2;
  const y = (canvas.height - h) / 2;
  ctx.fillStyle = 'rgba(8,14,20,0.74)';
  const r = 14;
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = accent;
  ctx.font = 'bold 40px ui-monospace, SFMono-Regular, Menlo, monospace';
  ctx.fillText(line1, canvas.width / 2, canvas.height / 2 - 20);
  ctx.fillStyle = 'rgba(190,240,255,0.92)';
  ctx.font = '32px ui-monospace, SFMono-Regular, Menlo, monospace';
  ctx.fillText(line2, canvas.width / 2, canvas.height / 2 + 22);
  texture.needsUpdate = true;
}

interface WpMarker {
  seq: number;
  pos: THREE.Vector3;
  alt: number;
  active: boolean;
  /** Reticle sprite (so compact mode can shrink far ones with distance). */
  reticle: THREE.Sprite;
  /** Near / base reticle scale before any distance shrink. */
  reticleBase: number;
  /** Static number-only tag (compact HUD, small missions only). Never redrawn. */
  numberTag: THREE.Sprite | null;
  disposables: Array<{ dispose: () => void }>;
}

/**
 * One reusable caption sprite. Slots are reassigned to whichever waypoints
 * currently deserve a caption, so the canvas + texture count is fixed by the
 * pool size instead of growing with the mission.
 */
interface CaptionSlot {
  sprite: THREE.Sprite;
  canvas: HTMLCanvasElement;
  texture: THREE.CanvasTexture;
  material: THREE.SpriteMaterial;
  /** Index into `markers` this slot currently captions, or -1 when parked. */
  markerIdx: number;
  lastText: string;
}

export function createWaypointSymbology(options: WaypointSymbologyOptions = {}): WaypointSymbology {
  const compact = options.compact === true;
  const group = new THREE.Group();

  // Shared assets (built once). Sprites use constant screen size in compact HUD
  // mode (sizeAttenuation off) and perspective size in the Sim World.
  const wpMat = new THREE.MeshStandardMaterial({ color: 0x22d3ee, emissive: 0x0891b2, emissiveIntensity: 0.5, roughness: 0.4 });
  const wpLineMat = new THREE.LineBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: compact ? 0.42 : 0.8 });
  const wpGeom = new THREE.SphereGeometry(SYMBOL_SCALE * 0.45, 12, 10);

  const reticleCanvas = document.createElement('canvas');
  reticleCanvas.width = 128;
  reticleCanvas.height = 128;
  const reticleTexture = new THREE.CanvasTexture(reticleCanvas);
  reticleTexture.colorSpace = THREE.SRGBColorSpace;
  drawReticle(reticleCanvas, reticleTexture, WP_CYAN);
  const reticleMat = new THREE.SpriteMaterial({ map: reticleTexture, transparent: true, depthTest: false, depthWrite: false, sizeAttenuation: !compact, opacity: 1 });

  const reticleActiveCanvas = document.createElement('canvas');
  reticleActiveCanvas.width = 128;
  reticleActiveCanvas.height = 128;
  const reticleActiveTexture = new THREE.CanvasTexture(reticleActiveCanvas);
  reticleActiveTexture.colorSpace = THREE.SRGBColorSpace;
  drawReticle(reticleActiveCanvas, reticleActiveTexture, WP_ACTIVE);
  const reticleActiveMat = new THREE.SpriteMaterial({ map: reticleActiveTexture, transparent: true, depthTest: false, depthWrite: false, sizeAttenuation: !compact });

  const sharedDisposables: Array<{ dispose: () => void }> = [
    wpMat, wpLineMat, wpGeom, reticleTexture, reticleMat, reticleActiveTexture, reticleActiveMat,
  ];

  // Markers are torn down and rebuilt when the mission changes; the caption pool
  // persists for the lifetime of the symbology. Separate sub-groups keep
  // disposeMarkers() from clearing the pool out of the scene.
  const markerGroup = new THREE.Group();
  markerGroup.name = 'wp-markers';
  const captionGroup = new THREE.Group();
  captionGroup.name = 'wp-captions';
  group.add(markerGroup);
  group.add(captionGroup);

  let markers: WpMarker[] = [];
  let signature = 0;
  let visible = true;
  const captionPool: CaptionSlot[] = [];
  let lastCaptionRefresh = -Infinity;

  function disposeMarkers(): void {
    for (let i = markerGroup.children.length - 1; i >= 0; i--) {
      const c = markerGroup.children[i]!;
      markerGroup.remove(c);
      // Line/LineSegments own a geometry built for this rebuild, so it must go.
      // The InstancedMesh borrows the SHARED wpGeom (disposing it would break
      // every later rebuild); dispose() releases only its instance buffers.
      if (c instanceof THREE.InstancedMesh) c.dispose();
      else if (c instanceof THREE.Line) c.geometry.dispose();
    }
    for (const m of markers) for (const d of m.disposables) d.dispose();
    markers = [];
  }

  function isActive(wp: Wp, activeSeq: number | null): boolean {
    return wp.active === true || (activeSeq != null && wp.seq === activeSeq);
  }

  /**
   * Change-detection hash over the mission. Runs on EVERY frame, so it must not
   * allocate per waypoint: the previous version joined a per-waypoint string,
   * building ~40 KB of garbage per frame on a 573-waypoint survey. A 32-bit FNV
   * walk over the same values costs nothing and compares just as reliably.
   */
  function sig(waypoints: Wp[], activeSeq: number | null): number {
    let h = 0x811c9dc5;
    const mix = (v: number) => {
      // Quantise to 0.1 m so float noise can't force a rebuild, matching the
      // toFixed(1) the string version used.
      h ^= Math.round(v * 10) | 0;
      h = Math.imul(h, 0x01000193);
    };
    mix(waypoints.length);
    mix(activeSeq ?? -1);
    for (const w of waypoints) {
      mix(w.seq);
      mix(w.position[0]);
      mix(w.position[1]);
      mix(w.position[2]);
      mix(isActive(w, activeSeq) ? 1 : 0);
    }
    return h >>> 0;
  }

  function rebuild(waypoints: Wp[], activeSeq: number | null): void {
    disposeMarkers();
    if (waypoints.length === 0) return;
    const n = waypoints.length;
    // Number tags are static, one texture each, so they only earn their keep on
    // a hand-built mission. A survey gets reticles + route line only.
    const wantNumberTags = compact && n <= NUMBER_TAG_BUDGET;

    const linePts: THREE.Vector3[] = [];
    // Perspective extras are batched: one InstancedMesh for every core sphere and
    // one LineSegments for every drop line, instead of two scene objects (and two
    // draw calls) per waypoint. At survey density the per-waypoint version alone
    // put ~1,100 extra draw calls on the frame.
    const cores = compact ? null : new THREE.InstancedMesh(wpGeom, wpMat, n);
    const dropPts: THREE.Vector3[] = [];
    const coreXform = new THREE.Matrix4();

    for (let i = 0; i < n; i++) {
      const wp = waypoints[i]!;
      const active = isActive(wp, activeSeq);
      const pos = nedToThree(wp.position, new THREE.Vector3());
      const alt = -wp.position[2];
      linePts.push(pos.clone());

      // Perspective mode keeps the solid core sphere + drop line; compact HUD
      // drops both (the sphere balloons up close and the drop lines clutter).
      if (cores) {
        cores.setMatrixAt(i, coreXform.makeTranslation(pos.x, pos.y, pos.z));
        dropPts.push(pos.clone(), new THREE.Vector3(pos.x, 0, pos.z));
      }

      // Billboard target reticle at the true position (active = amber + larger).
      const reticle = new THREE.Sprite(active ? reticleActiveMat : reticleMat);
      const reticleBase = compact
        ? COMPACT_RETICLE * (active ? ACTIVE_BOOST : 1)
        : SYMBOL_SCALE * 2.4 * (active ? ACTIVE_BOOST : 1);
      reticle.scale.set(reticleBase, reticleBase, 1);
      reticle.position.copy(pos);
      reticle.renderOrder = 997;
      markerGroup.add(reticle);

      // Small NUMBER tag above each compact reticle so a hand-built route stays
      // readable (like the map) without a full caption on every waypoint. seq is
      // our 0-based internal index (HOME stripped, renumbered from 0); the number
      // the map + FC show is seq + 1. Live captions come from the pool instead.
      let numberTag: THREE.Sprite | null = null;
      const disposables: Array<{ dispose: () => void }> = [];
      if (wantNumberTags) {
        const tagCanvas = document.createElement('canvas');
        tagCanvas.width = 128;
        tagCanvas.height = 64;
        const tagTexture = new THREE.CanvasTexture(tagCanvas);
        tagTexture.colorSpace = THREE.SRGBColorSpace;
        drawWpNumber(tagCanvas, tagTexture, `${wp.seq + 1}`, active ? WP_ACTIVE : WP_CYAN);
        const tagMat = new THREE.SpriteMaterial({ map: tagTexture, transparent: true, depthTest: false, depthWrite: false, sizeAttenuation: false, opacity: 0.95 });
        numberTag = new THREE.Sprite(tagMat);
        numberTag.scale.set(COMPACT_NUM_W, COMPACT_NUM_H, 1);
        numberTag.center.set(0.5, -0.7); // sit just above the reticle box
        numberTag.position.copy(pos);
        numberTag.renderOrder = 999;
        markerGroup.add(numberTag);
        disposables.push(tagMat, tagTexture);
      }

      markers.push({ seq: wp.seq, pos, alt, active, reticle, reticleBase, numberTag, disposables });
    }

    if (cores) {
      cores.instanceMatrix.needsUpdate = true;
      markerGroup.add(cores);
      markerGroup.add(new THREE.LineSegments(
        new THREE.BufferGeometry().setFromPoints(dropPts),
        wpLineMat,
      ));
    }
    if (linePts.length > 1) {
      markerGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(linePts), wpLineMat));
    }

    // Every slot now points at a stale marker index; force a full reassign.
    for (const slot of captionPool) {
      slot.markerIdx = -1;
      slot.lastText = '';
      slot.sprite.visible = false;
    }
    lastCaptionRefresh = -Infinity;
  }

  const poolSize = compact ? CAPTION_POOL_COMPACT : CAPTION_POOL_PERSPECTIVE;

  /** Grow the caption pool on demand, up to `poolSize`. Built lazily so a scene
      that never shows waypoints never allocates a canvas. */
  function slot(i: number): CaptionSlot {
    const existing = captionPool[i];
    if (existing) return existing;
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 128;
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false, sizeAttenuation: !compact, opacity: compact ? 0.96 : 1 });
    const sprite = new THREE.Sprite(material);
    if (compact) {
      // Constant screen size: nudge the caption a fixed amount ABOVE the reticle
      // via the sprite anchor (a world offset is imperceptible when
      // sizeAttenuation is off), so it never overlaps the target box.
      sprite.scale.set(COMPACT_LABEL_W, COMPACT_LABEL_H, 1);
      sprite.center.set(0.5, -0.4);
    } else {
      sprite.scale.set(SYMBOL_SCALE * 4, SYMBOL_SCALE * 2, 1);
    }
    sprite.renderOrder = 999;
    sprite.visible = false;
    captionGroup.add(sprite);
    const created: CaptionSlot = { sprite, canvas, texture, material, markerIdx: -1, lastText: '' };
    captionPool[i] = created;
    return created;
  }

  /**
   * Choose which markers deserve a live caption.
   *
   * Compact HUD keeps its established rule (the active waypoint + the next one).
   *
   * Perspective spreads captions EVENLY along the route by stride, not by picking
   * the nearest N. Nearest-N looks correct in a unit test and is wrong in the air:
   * every label bunches into one spot and the rest of the route reads as bare
   * outlines, which is exactly how a survey lost its highway. Even sampling keeps
   * the whole path legible from any camera distance, and it makes the slot-to-marker
   * mapping STABLE as you fly, so slots only redraw when their text changes rather
   * than every time the ordering shuffles.
   *
   * The route's ends, the nearest waypoint and the active one are always included,
   * so the bits a pilot navigates by never drop out.
   */
  function selectCaptioned(from: THREE.Vector3, out: number[]): void {
    out.length = 0;
    const n = markers.length;
    if (n === 0) return;
    if (compact) {
      let activeIdx = markers.findIndex((m) => m.active);
      if (activeIdx < 0) activeIdx = 0;
      out.push(activeIdx);
      if (activeIdx + 1 < n) out.push(activeIdx + 1);
      return;
    }

    // The leading slots are a FIXED stride sample: their contents depend only on
    // the route length, so those slots keep the same waypoint for the whole flight
    // and never redraw from reassignment. The two volatile picks (nearest, active)
    // go in TRAILING slots, so when they change they disturb only themselves.
    // Putting them anywhere else shifts every later slot by one and triggers a
    // full-pool redraw each time the nearest waypoint changes.
    const reserved = 2;
    const strideSlots = Math.max(1, poolSize - reserved);
    const stride = Math.max(1, Math.ceil(n / strideSlots));
    for (let i = 0; i < n && out.length < strideSlots; i += stride) out.push(i);
    // Make sure the far end of the route is labelled, without shifting anything.
    if (out[out.length - 1] !== n - 1) {
      if (out.length < strideSlots) out.push(n - 1);
      else out[out.length - 1] = n - 1;
    }

    let nearest = 0;
    let nearestD = Infinity;
    for (let i = 0; i < n; i++) {
      const d = from.distanceToSquared(markers[i]!.pos);
      if (d < nearestD) { nearestD = d; nearest = i; }
    }
    const activeIdx = markers.findIndex((m) => m.active);
    for (const extra of [activeIdx, nearest]) {
      if (extra >= 0 && extra < n && !out.includes(extra) && out.length < poolSize) out.push(extra);
    }
  }

  const captioned: number[] = [];

  /**
   * Point the caption pool at the currently interesting waypoints and refresh
   * their text. Redraws only when a slot's rendered string actually changes, so a
   * stationary vehicle costs nothing. Throttled by the caller.
   */
  function refreshCaptions(from: THREE.Vector3): void {
    selectCaptioned(from, captioned);
    for (let i = 0; i < poolSize; i++) {
      const markerIdx = captioned[i];
      if (markerIdx === undefined) {
        const existing = captionPool[i];
        if (existing) { existing.sprite.visible = false; existing.markerIdx = -1; }
        continue;
      }
      const m = markers[markerIdx]!;
      const s = slot(i);
      if (s.markerIdx !== markerIdx) {
        s.markerIdx = markerIdx;
        if (compact) s.sprite.position.copy(m.pos);
        else s.sprite.position.set(m.pos.x, m.pos.y + SYMBOL_SCALE * 2.1, m.pos.z);
      }
      s.sprite.visible = true;
      const dist = Math.round(from.distanceTo(m.pos));
      const line1 = `WP ${m.seq + 1}`;
      const line2 = `${dist}m · ${Math.round(m.alt)}m`;
      const text = `${line1}|${line2}`;
      if (text === s.lastText) continue;
      s.lastText = text;
      drawWpLabel(s.canvas, s.texture, line1, line2, m.active ? WP_ACTIVE : WP_CYAN);
    }
  }

  /** Compact mode shrinks far reticles slightly for depth (never grows them). */
  function refreshReticleDepth(from: THREE.Vector3): void {
    if (!compact) return;
    for (const m of markers) {
      const t = Math.min(1, Math.max(0, (from.distanceTo(m.pos) - 40) / 600));
      const s = m.reticleBase * (1 - (1 - COMPACT_MIN_SHRINK) * t);
      m.reticle.scale.set(s, s, 1);
    }
  }

  return {
    group,

    update(waypoints, flownPos, activeSeq) {
      const s = sig(waypoints, activeSeq);
      if (s !== signature) {
        rebuild(waypoints, activeSeq);
        signature = s;
      }
      group.visible = visible;
      // Hidden symbology does no per-frame work at all. setVisible() used to only
      // clear group.visible, so toggling waypoints off still paid the full
      // caption cost every frame.
      if (!visible) return;
      const now = performance.now();
      if (now - lastCaptionRefresh < CAPTION_REFRESH_MS) return;
      lastCaptionRefresh = now;
      refreshCaptions(flownPos);
      refreshReticleDepth(flownPos);
    },

    setVisible(on) {
      visible = on;
      group.visible = on;
    },

    dispose() {
      disposeMarkers();
      for (const slot of captionPool) {
        captionGroup.remove(slot.sprite);
        slot.material.dispose();
        slot.texture.dispose();
      }
      captionPool.length = 0;
      for (const d of sharedDisposables) d.dispose();
    },
  };
}
