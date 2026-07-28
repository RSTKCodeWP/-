/**
 * Turns an `ardudeck-frame` crate FrameBlueprint (JSON, from the
 * `frame:generate-blueprint` IPC call) into a three.js `Template` compatible
 * with sim-world-scene's `buildModelFrame`/`installModel` machinery, so a
 * procedurally-generated airframe can stand in for the static GLB models.
 *
 * Coordinate mapping: the blueprint is Z-up (motors sit in the local x/y
 * plane; a motor's thrust axis and its prop disc's normal both point +Z).
 * three.js is Y-up. All parts are built in an inner group using the
 * blueprint's own coordinates, then that group is wrapped in an outer
 * THREE.Group rotated -90 deg about X, which maps blueprint +Z -> three +Y
 * (thrust now points up, matching every other vehicle template).
 */

import * as THREE from 'three';

export interface FrameBuilderTemplate {
  group: THREE.Group;
  spinAxis: 'x' | 'y' | 'z';
  topY: number;
}

interface Vec3J { x: number; y: number; z: number }
interface QuatJ { w: number; x: number; y: number; z: number }

type PartDimsJ =
  | { shape: 'box'; l: number; w: number; h: number }
  | { shape: 'tube'; r: number; h: number }
  | { shape: 'disc'; r: number; thick: number };

type PartRoleJ = 'arm' | 'plate' | 'motor_bell' | 'motor_stator' | 'prop' | 'esc' | 'stack' | 'servo' | 'vane' | 'boom' | 'battery' | 'gps' | 'antenna';
type MaterialHintJ = 'carbon' | 'aluminum' | 'plastic_dark' | 'metal' | 'prop_translucent' | 'pcb' | 'heatshrink' | 'heatsink';

interface PartJ {
  kind: 'box' | 'tube' | 'disc' | 'blade' | 'standoff' | 'vane';
  role: PartRoleJ;
  dims: PartDimsJ;
  position: Vec3J;
  rotation: QuatJ;
  material_hint: MaterialHintJ;
  spin: { axis: Vec3J; dir: number } | null;
  /** Parts sharing a `group` (a motor's blades + blur disc) spin as one rotor
      under a single pivot. Absent on static parts. */
  group?: number;
}

interface FrameBlueprintJ {
  parts: PartJ[];
  bounds: { min: Vec3J; max: Vec3J };
}

/** Generated frames render at TRUE metric scale: the blueprint is already in
    metres and the sim world is metric (1 unit = 1 m, home pad 6 m dia, range
    rings at 25/50/100/200 m), so a 1.6 m octa is 1.6 m in the world. Only frames
    whose span falls below this floor are scaled up, so a micro/whoop stays
    selectable without visibly inflating anything real. */
const MIN_VISUAL_SPAN = 0.5;

// ─── Procedural textures (generated on a canvas at load - no image assets) ────
// The blueprint stays render-agnostic: it only ever emits abstract material
// hints. This module is the ArduDeck (three.js) interpretation of those hints,
// turning each into a richly textured material. A future non-three renderer
// implements the same hint -> material mapping its own way.
function texFromCanvas(draw: (ctx: CanvasRenderingContext2D, s: number) => void, size: number, repeat: number): THREE.Texture {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (ctx) draw(ctx, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(repeat, repeat);
  tex.anisotropy = 4;
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

// Carbon-fibre 2/2 twill: the over-two/under-two float shifts by one tow each
// row, giving the characteristic diagonal rib - NOT a checkerboard. Contrast is
// deliberately low (real carbon is near-monochrome dark grey); the weave reads
// from the diagonal rib + a faint fibre sheen, not from tile contrast.
function drawCarbon(ctx: CanvasRenderingContext2D, s: number): void {
  const cells = 32;
  const cell = s / cells;
  ctx.fillStyle = '#191c20';
  ctx.fillRect(0, 0, s, s);
  for (let cy = 0; cy < cells; cy++) {
    for (let cx = 0; cx < cells; cx++) {
      const warpOnTop = ((((cx - cy) % 4) + 4) % 4) < 2; // 2/2 twill diagonal
      ctx.fillStyle = warpOnTop ? '#22262c' : '#171a1e';
      ctx.fillRect(cx * cell, cy * cell, cell, cell);
      // one sheen line per tow, along the tow's direction (warp = horizontal).
      ctx.strokeStyle = 'rgba(140,152,168,0.05)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      if (warpOnTop) { ctx.moveTo(cx * cell, cy * cell + cell * 0.5); ctx.lineTo(cx * cell + cell, cy * cell + cell * 0.5); }
      else { ctx.moveTo(cx * cell + cell * 0.5, cy * cell); ctx.lineTo(cx * cell + cell * 0.5, cy * cell + cell); }
      ctx.stroke();
    }
  }
}

// Brushed aluminium: light base with many faint circumferential streaks.
function drawBrushed(ctx: CanvasRenderingContext2D, s: number): void {
  ctx.fillStyle = '#b7bdc4';
  ctx.fillRect(0, 0, s, s);
  for (let i = 0; i < s * 4; i++) {
    const y = Math.random() * s;
    const l = 150 + ((Math.random() * 85) | 0);
    ctx.strokeStyle = `rgba(${l},${l},${l + 4},0.05)`;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(s, y + (Math.random() - 0.5) * 2);
    ctx.stroke();
  }
}

// Matte plastic: dark base with a fine dual-tone speckle so flat faces aren't
// dead-flat under lighting.
function drawPlastic(ctx: CanvasRenderingContext2D, s: number): void {
  ctx.fillStyle = '#2c3037';
  ctx.fillRect(0, 0, s, s);
  const dots = (s * s) * 0.06;
  for (let i = 0; i < dots; i++) {
    ctx.fillStyle = Math.random() < 0.5 ? 'rgba(0,0,0,0.16)' : 'rgba(255,255,255,0.05)';
    ctx.fillRect(Math.random() * s, Math.random() * s, 1, 1);
  }
}

// PCB: green solder mask, meandering copper traces, gold pads, a black IC and a
// little silkscreen.
function drawPcb(ctx: CanvasRenderingContext2D, s: number): void {
  ctx.fillStyle = '#0c3b22';
  ctx.fillRect(0, 0, s, s);
  ctx.strokeStyle = 'rgba(36,130,78,0.85)';
  ctx.lineWidth = Math.max(1, s / 128);
  for (let i = 0; i < 26; i++) {
    ctx.beginPath();
    let x = Math.random() * s;
    let y = Math.random() * s;
    ctx.moveTo(x, y);
    for (let seg = 0; seg < 4; seg++) {
      if (Math.random() < 0.5) x += (Math.random() - 0.5) * s * 0.4;
      else y += (Math.random() - 0.5) * s * 0.4;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  for (let i = 0; i < 44; i++) {
    ctx.fillStyle = '#c9a227';
    ctx.beginPath();
    ctx.arc(Math.random() * s, Math.random() * s, s / 64, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = '#0a0a0c';
  ctx.fillRect(s * 0.36, s * 0.36, s * 0.28, s * 0.28);
  ctx.fillStyle = 'rgba(220,230,225,0.45)';
  ctx.fillRect(s * 0.1, s * 0.1, s * 0.22, Math.max(1, s / 160));
}

// Finned aluminium heatsink: parallel bright-ridge / dark-valley bands = fins.
function drawHeatsink(ctx: CanvasRenderingContext2D, s: number): void {
  const fins = 16;
  const w = s / fins;
  for (let i = 0; i < fins; i++) {
    const g = ctx.createLinearGradient(i * w, 0, (i + 1) * w, 0);
    g.addColorStop(0, '#878d95');
    g.addColorStop(0.5, '#d4dae0');
    g.addColorStop(1, '#878d95');
    ctx.fillStyle = g;
    ctx.fillRect(i * w, 0, w, s);
  }
}

const CARBON_TEX = texFromCanvas(drawCarbon, 256, 10);
const BRUSH_TEX = texFromCanvas(drawBrushed, 256, 3);
const PLASTIC_TEX = texFromCanvas(drawPlastic, 256, 6);
const PCB_TEX = texFromCanvas(drawPcb, 256, 1);

// Shared textured materials (safe to reuse across cloned templates - three.js
// shares textures/materials by reference and the model templates already do the
// same). `color` is left white so the procedural map shows through unmodified.
const MAT_CARBON = new THREE.MeshStandardMaterial({ map: CARBON_TEX, color: 0xffffff, roughness: 0.55, metalness: 0.3 });
const MAT_PLASTIC_DARK = new THREE.MeshStandardMaterial({ map: PLASTIC_TEX, color: 0xffffff, roughness: 0.75, metalness: 0.08 });
const MAT_ALUMINUM = new THREE.MeshStandardMaterial({ map: BRUSH_TEX, color: 0xffffff, roughness: 0.4, metalness: 0.7 });
const MAT_PCB = new THREE.MeshStandardMaterial({ map: PCB_TEX, color: 0xffffff, roughness: 0.55, metalness: 0.15 });
// Heatshrink: near-black, smooth and slightly glossy (low roughness) - what an
// ESC actually looks like wrapped. No texture: heatshrink reads by its sheen.
const MAT_HEATSHRINK = new THREE.MeshStandardMaterial({ color: 0x131519, roughness: 0.32, metalness: 0.12 });
const HEATSINK_TEX = texFromCanvas(drawHeatsink, 256, 1);
const MAT_HEATSINK = new THREE.MeshStandardMaterial({ map: HEATSINK_TEX, color: 0xffffff, roughness: 0.42, metalness: 0.7 });
// Base prop-blur disc material. Cloned per frame so the render loop can fade
// each vehicle's discs by RPM (invisible at rest, a faint blur when spinning)
// without touching other vehicles. Base opacity 0 = hidden until driven.
// depthWrite:false so a transparent (even fully-invisible) disc never writes
// depth and clips the blades / pad behind it - the crescent artifacts near props.
const MAT_PROP = new THREE.MeshStandardMaterial({ color: 0x0b0d10, roughness: 0.4, transparent: true, opacity: 0, depthWrite: false });

function materialFor(hint: MaterialHintJ): THREE.MeshStandardMaterial {
  switch (hint) {
    case 'carbon': return MAT_CARBON;
    case 'plastic_dark': return MAT_PLASTIC_DARK;
    case 'aluminum': return MAT_ALUMINUM;
    case 'metal': return MAT_ALUMINUM;
    case 'prop_translucent': return MAT_PROP;
    case 'pcb': return MAT_PCB;
    case 'heatshrink': return MAT_HEATSHRINK;
    case 'heatsink': return MAT_HEATSINK;
    default: return MAT_CARBON;
  }
}

// World size (metres) one full texture tile should cover per material, so texel
// density is roughly constant regardless of part size. Solid materials (no map)
// are absent - they need no UV scaling.
const TILE_WORLD: Partial<Record<MaterialHintJ, number>> = {
  carbon: 0.16,
  plastic_dark: 0.12,
  aluminum: 0.2,
  metal: 0.2,
  pcb: 0.3,
  heatsink: 0.09,
};

/**
 * Per-part material with UV repeat set from the part's real dimensions, so the
 * texture keeps a constant world scale instead of stretching. Tubes get proper
 * circumference/length repeat (the fix for stretched arm textures); boxes use
 * their largest dimension; solid (map-less) materials pass straight through.
 */
function scaledMaterial(part: PartJ, base: THREE.MeshStandardMaterial): THREE.MeshStandardMaterial {
  if (!base.map) return base;
  const tile = TILE_WORLD[part.material_hint] ?? 0.15;
  const d = part.dims;
  const tex = base.map.clone();
  tex.needsUpdate = true;
  if (d.shape === 'tube') {
    tex.repeat.set(Math.max(1, (2 * Math.PI * d.r) / tile), Math.max(0.5, d.h / tile));
  } else if (d.shape === 'disc') {
    tex.repeat.set(1, 1);
  } else {
    const mx = Math.max(d.l, d.w, d.h);
    tex.repeat.set(Math.max(0.5, mx / tile), Math.max(0.5, mx / tile));
  }
  const m = base.clone();
  m.map = tex;
  return m;
}

/** Build a mesh for one part. Keyed off `dims.shape` (always one of the three
    PartDims variants) rather than `kind`, since `kind` values like
    vane/standoff/blade still carry Box dims today - this covers those and any
    future shape/kind combination the crate adds. */
function meshForPart(part: PartJ): THREE.Mesh {
  const mat = scaledMaterial(part, materialFor(part.material_hint));
  const dims = part.dims;
  let geom: THREE.BufferGeometry;
  let alignToZ = false;

  if (dims.shape === 'tube') {
    geom = new THREE.CylinderGeometry(dims.r, dims.r, dims.h, 16);
    alignToZ = true;
  } else if (dims.shape === 'disc') {
    geom = new THREE.CylinderGeometry(dims.r, dims.r, dims.thick, 24);
    alignToZ = true;
  } else if (dims.shape === 'box') {
    geom = new THREE.BoxGeometry(dims.l, dims.w, dims.h);
  } else {
    // Defensive fallback for a shape the type system doesn't know about yet.
    geom = new THREE.BoxGeometry(0.02, 0.02, 0.02);
  }

  const mesh = new THREE.Mesh(geom, mat);
  mesh.quaternion.set(part.rotation.x, part.rotation.y, part.rotation.z, part.rotation.w);
  if (alignToZ) {
    // Cylinders run along local Y by default; rotate +90deg about X (in the
    // part's own already-applied rotation frame) so the tube/disc axis runs
    // along blueprint +Z - the motor's thrust axis / the prop disc's normal.
    mesh.rotateX(Math.PI / 2);
  }
  return mesh;
}

/**
 * Build a Template from an ardudeck-frame FrameBlueprint (as returned by the
 * `frame:generate-blueprint` IPC channel - passed through as `unknown` there
 * since only this module needs to know its shape).
 */
export function buildTemplateFromBlueprint(blueprint: unknown): FrameBuilderTemplate {
  const bp = blueprint as FrameBlueprintJ;

  const innerGroup = new THREE.Group();
  const allParts = bp.parts ?? [];

  // Static parts sit at their absolute blueprint position.
  for (const part of allParts) {
    if (part.spin !== null) continue;
    const mesh = meshForPart(part);
    mesh.position.set(part.position.x, part.position.y, part.position.z);
    innerGroup.add(mesh);
  }

  // Spinning parts are bucketed by `group` (a motor's blades + blur disc) so
  // each rotor turns as one unit. The pivot sits at the group's hub - the disc
  // is hub-centred, so its position is the pivot; parts hang off it in local
  // coordinates. Parts without a group each become their own singleton rotor.
  const groups = new Map<string, PartJ[]>();
  let singleton = 0;
  for (const part of allParts) {
    if (part.spin === null) continue;
    const key = part.group !== undefined ? `g${part.group}` : `s${singleton++}`;
    const bucket = groups.get(key);
    if (bucket) bucket.push(part);
    else groups.set(key, [part]);
  }

  // One blur-disc material per generated frame (not the shared module one) so
  // the render loop can fade THIS vehicle's discs by RPM in isolation. Tagged
  // meshes let sim-world-scene collect it after the template is cloned.
  const discMat = MAT_PROP.clone();

  let propIndex = 0;
  for (const parts of groups.values()) {
    const hubSource = parts.find((p) => p.kind === 'disc') ?? parts[0]!;
    const hub = hubSource.position;
    const pivot = new THREE.Group();
    pivot.name = `prop_${propIndex++}`;
    pivot.position.set(hub.x, hub.y, hub.z);
    for (const part of parts) {
      const mesh = meshForPart(part);
      if (part.kind === 'disc') mesh.material = discMat;
      mesh.position.set(part.position.x - hub.x, part.position.y - hub.y, part.position.z - hub.z);
      mesh.userData.propLayer = part.kind === 'disc' ? 'disc' : 'blade';
      pivot.add(mesh);
    }
    innerGroup.add(pivot);
  }

  const outerGroup = new THREE.Group();
  outerGroup.rotation.x = -Math.PI / 2; // blueprint +Z (thrust up) -> three +Y (up)
  outerGroup.add(innerGroup);
  outerGroup.updateMatrixWorld(true);

  // True metric scale: the blueprint is already in metres, so scale 1:1 and
  // only scale UP micro frames that fall below the visibility floor. Then rest
  // the lowest point (landing feet / body) just above the pad's top face.
  const box = new THREE.Box3().setFromObject(outerGroup);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const span = Math.max(size.x, size.z, 1e-3);
  const s = span < MIN_VISUAL_SPAN ? MIN_VISUAL_SPAN / span : 1.0;
  outerGroup.scale.setScalar(s);
  // The pad disc/ring sit at y ~= 0.02-0.03, so a small clearance keeps the
  // frame's feet on top of it rather than clipping through.
  const GROUND_CLEARANCE = 0.03;
  outerGroup.position.set(-center.x * s, -box.min.y * s + GROUND_CLEARANCE, -center.z * s);
  outerGroup.updateMatrixWorld(true);

  const finalBox = new THREE.Box3().setFromObject(outerGroup);
  const topY = finalBox.max.y > 0 ? finalBox.max.y : 0.5;

  // Each prop pivot is a child of the UNROTATED inner group, so its local frame
  // is still the blueprint's Z-up frame. Object3D rotation is applied in the
  // object's own local frame, so the rotor spins about local +Z (the thrust
  // axis / disc normal) - the outer group's -90deg X rotation only reorients
  // the whole model in the world, it does not change the pivot's local spin
  // axis. Spinning about Y here would tumble the blades instead of turning them.
  return { group: outerGroup, spinAxis: 'z', topY };
}
