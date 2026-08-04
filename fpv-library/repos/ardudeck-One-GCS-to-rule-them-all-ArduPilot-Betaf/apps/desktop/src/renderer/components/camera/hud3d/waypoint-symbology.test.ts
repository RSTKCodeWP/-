// @vitest-environment jsdom
/**
 * The cost of the 3D waypoint symbology must be bounded by the POOL, not by the
 * mission length. A generated survey (TOPAS coverage plans routinely exceed 500
 * waypoints) previously built a canvas + GPU texture per waypoint and redrew
 * every one of them on every frame, which pinned the Sim World at ~1 fps.
 */
import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import { createWaypointSymbology, type Wp } from './waypoint-symbology';

function mission(n: number): Wp[] {
  // A survey-like lawnmower pattern, all within a few hundred metres.
  return Array.from({ length: n }, (_, i) => ({
    seq: i,
    position: [i * 12, (i % 2) * 80, -50] as [number, number, number],
  }));
}

/** Every sprite that carries its own canvas-backed texture. */
function texturedSprites(root: THREE.Object3D): THREE.Sprite[] {
  const out: THREE.Sprite[] = [];
  root.traverse((o) => {
    if (o instanceof THREE.Sprite) out.push(o);
  });
  return out;
}

function distinctTextures(root: THREE.Object3D): number {
  const maps = new Set<unknown>();
  root.traverse((o) => {
    const mat = (o as THREE.Sprite).material as THREE.SpriteMaterial | undefined;
    if (mat && 'map' in mat && mat.map) maps.add(mat.map);
  });
  return maps.size;
}

describe('waypoint symbology scales to generated surveys', () => {
  it('keeps texture count bounded as the mission grows', () => {
    const from = new THREE.Vector3(0, 50, 0);

    const small = createWaypointSymbology();
    small.update(mission(20), from, 0);
    const smallTextures = distinctTextures(small.group);

    const survey = createWaypointSymbology();
    survey.update(mission(573), from, 0);
    const surveyTextures = distinctTextures(survey.group);

    // Two shared reticle textures + at most one per caption slot (pool of 48). The
    // old code allocated one 256x128 canvas texture per waypoint, ~75 MB at 573 WPs,
    // and redrew every one of them every frame.
    expect(surveyTextures).toBeLessThanOrEqual(52);
    // A 28x bigger mission must not cost meaningfully more texture memory.
    expect(surveyTextures - smallTextures).toBeLessThanOrEqual(30);

    small.dispose();
    survey.dispose();
  });

  it('caps live captions well below the waypoint count', () => {
    const sym = createWaypointSymbology();
    sym.update(mission(573), new THREE.Vector3(0, 50, 0), 0);

    // 573 reticles are expected; captions are not.
    const captions = sym.group.getObjectByName('wp-captions')!;
    const markers = sym.group.getObjectByName('wp-markers')!;
    expect(texturedSprites(markers).length).toBe(573); // reticles, one per WP
    expect(texturedSprites(captions).length).toBeLessThanOrEqual(48);
    sym.dispose();
  });

  it('spreads captions along the whole route, not bunched at the camera', () => {
    // Regression: picking the nearest N clustered every label in one place and
    // left the rest of a survey as bare outlines, which read as "waypoints gone".
    const n = 573;
    const sym = createWaypointSymbology();
    sym.update(mission(n), new THREE.Vector3(0, 50, 0), null);

    const captions = sym.group.getObjectByName('wp-captions')!;
    const shown = captions.children.filter((c) => c.visible);
    expect(shown.length).toBeGreaterThan(20);

    // Captions must span the route's full extent, not a small neighbourhood.
    // mission() lays waypoints out along +north, which maps to three.z.
    const zs = shown.map((c) => c.position.z);
    const markers = sym.group.getObjectByName('wp-markers')!;
    const allZ = markers.children.filter((c) => c instanceof THREE.Sprite).map((c) => c.position.z);
    const routeSpan = Math.max(...allZ) - Math.min(...allZ);
    const captionSpan = Math.max(...zs) - Math.min(...zs);
    expect(captionSpan).toBeGreaterThan(routeSpan * 0.8);

    // Both ends of the route keep a label.
    expect(Math.min(...zs)).toBeCloseTo(Math.min(...allZ), 1);
    expect(Math.max(...zs)).toBeCloseTo(Math.max(...allZ), 1);
    sym.dispose();
  });

  it('keeps caption slots on the same waypoints as the viewer moves', () => {
    // Slot stability is what stops the whole pool redrawing its canvases whenever
    // the camera moves. Compared per SLOT (children order == slot order), not
    // sorted, because a sorted compare hides a one-place shift as a total change.
    const sym = createWaypointSymbology();
    const wps = mission(200);
    sym.update(wps, new THREE.Vector3(0, 50, 0), null);
    const captions = sym.group.getObjectByName('wp-captions')!;
    const snapshot = () => captions.children.map((c) => (c.visible ? c.position.z : null));
    const before = snapshot();

    // Move the viewer a long way down the route and refresh past the throttle.
    const later = performance.now() + 1000;
    while (performance.now() < later) { /* spin past CAPTION_REFRESH_MS */ }
    sym.update(wps, new THREE.Vector3(0, 50, -1500), null);
    const after = snapshot();

    const moved = before.filter((z, i) => z !== after[i]).length;
    // Only the two trailing volatile slots (nearest + active) may reassign.
    expect(moved).toBeLessThanOrEqual(2);
    sym.dispose();
  });

  it('batches per-waypoint geometry instead of one object per waypoint', () => {
    const sym = createWaypointSymbology();
    sym.update(mission(573), new THREE.Vector3(0, 50, 0), 0);

    let meshes = 0;
    let lines = 0;
    sym.group.traverse((o) => {
      if (o instanceof THREE.InstancedMesh) return; // batched cores are fine
      if (o instanceof THREE.Mesh) meshes++;
      if (o instanceof THREE.Line) lines++;
    });
    // Previously: one core Mesh + one drop Line per waypoint (~1,146 objects).
    expect(meshes).toBe(0);
    expect(lines).toBeLessThanOrEqual(2); // merged drop lines + the route line
    sym.dispose();
  });

  it('does not accumulate objects across repeated frames', () => {
    const sym = createWaypointSymbology();
    const wps = mission(573);
    const from = new THREE.Vector3(0, 50, 0);
    sym.update(wps, from, 0);

    let count = 0;
    sym.group.traverse(() => { count++; });

    for (let i = 0; i < 30; i++) sym.update(wps, from, 0);

    let after = 0;
    sym.group.traverse(() => { after++; });
    expect(after).toBe(count);
    sym.dispose();
  });

  it('rebuilds when the mission actually changes', () => {
    const sym = createWaypointSymbology();
    const from = new THREE.Vector3(0, 50, 0);
    sym.update(mission(10), from, 0);
    let first = 0;
    sym.group.traverse(() => { first++; });

    sym.update(mission(40), from, 0);
    let second = 0;
    sym.group.traverse(() => { second++; });
    expect(second).toBeGreaterThan(first);
    sym.dispose();
  });

  it('hidden symbology stays hidden after an update', () => {
    const sym = createWaypointSymbology();
    sym.setVisible(false);
    sym.update(mission(573), new THREE.Vector3(0, 50, 0), 0);
    expect(sym.group.visible).toBe(false);
    sym.dispose();
  });
});
