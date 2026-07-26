/**
 * Three.js custom layer for MapLibre GL — renders mission flight path
 * and drop lines at altitude using proper 3D geometry.
 *
 * Waypoint markers are rendered as HTML elements projected to screen space
 * on each frame — always face camera, consistent pixel sizing, identical to 2D.
 *
 * Uses MapLibre's shared WebGL context and depth buffer (renderingMode: '3d')
 * so Three.js objects correctly occlude/clip with terrain and buildings.
 *
 * Follows the official MapLibre + Three.js pattern:
 *   https://maplibre.org/maplibre-gl-js/docs/examples/add-a-3d-model-using-threejs/
 */
import * as THREE from 'three';
import maplibregl, { type CustomLayerInterface, type CustomRenderMethodInput } from 'maplibre-gl';

// ─── Public types ────────────────────────────────────────────────────────────

export interface MissionLayerWaypoint {
  seq: number;
  lon: number;
  lat: number;
  displayAgl: number;   // meters AGL at this location
  groundElev: number;   // terrain elevation MSL at this waypoint
  color: string;        // resolved marker color (command or segment-aware)
  displayText: string;  // shape char or sequence number, e.g. "▲" or "5"
}

export interface MissionLayerData {
  waypoints: MissionLayerWaypoint[];
  selectedSeq: number | null;
  terrainExaggeration: number;
  segmentColors: string[]; // hex color per path segment (length = waypoints.length - 1)
}

export interface MissionThreeJsLayer {
  layer: CustomLayerInterface;
  updateData: (data: MissionLayerData) => void;
  setMarkerContainer: (container: HTMLDivElement | null) => void;
  dispose: () => void;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const FLIGHT_PATH_WIDTH = 8; // meters — ribbon width, thicker when closer via perspective
const DROP_LINE_COLOR = 0x9ca3af; // gray-400
const DROP_LINE_OPACITY = 0.5;
const MARKER_SIZE = 28;
const MARKER_SELECTED_SIZE = 32;

// ─── Factory ─────────────────────────────────────────────────────────────────

export function createMissionThreeJsLayer(
  onWaypointClick?: (seq: number) => void,
): MissionThreeJsLayer {
  let map: maplibregl.Map | null = null;
  let renderer: THREE.WebGLRenderer | null = null;
  const camera = new THREE.Camera();
  const scene = new THREE.Scene();

  // Model transform params — set during rebuildScene
  let modelTransform = {
    translateX: 0,
    translateY: 0,
    translateZ: 0,
    scale: 1,
  };

  // Precomputed rotation matrix (constant π/2 around X)
  const rotationX = new THREE.Matrix4().makeRotationAxis(
    new THREE.Vector3(1, 0, 0),
    Math.PI / 2,
  );

  // WebGL scene objects — ribbon meshes for flight path, GL lines for drop lines
  const flightPathSegments: { mesh: THREE.Mesh; geometry: THREE.BufferGeometry; material: THREE.MeshBasicMaterial }[] = [];
  let dropLinesObj: THREE.LineSegments | null = null;

  // DOM marker overlay
  let markerContainer: HTMLDivElement | null = null;

  interface DomMarker {
    seq: number;
    localX: number;
    localY: number;
    localZ: number;
    element: HTMLDivElement;
  }
  const domMarkers: DomMarker[] = [];

  // ─── Scene management ────────────────────────────────────────────────────

  function clearScene() {
    for (const seg of flightPathSegments) {
      scene.remove(seg.mesh);
      seg.geometry.dispose();
      seg.material.dispose();
    }
    flightPathSegments.length = 0;

    if (dropLinesObj) {
      scene.remove(dropLinesObj);
      dropLinesObj.geometry.dispose();
      (dropLinesObj.material as THREE.Material).dispose();
      dropLinesObj = null;
    }

    for (const m of domMarkers) {
      m.element.remove();
    }
    domMarkers.length = 0;
  }

  function rebuildScene(data: MissionLayerData) {
    clearScene();
    const { waypoints, selectedSeq, terrainExaggeration } = data;
    if (waypoints.length === 0) return;

    // Reference point = centroid of waypoints
    let sumLon = 0, sumLat = 0;
    for (const wp of waypoints) {
      sumLon += wp.lon;
      sumLat += wp.lat;
    }
    const refLon = sumLon / waypoints.length;
    const refLat = sumLat / waypoints.length;

    const refMc = maplibregl.MercatorCoordinate.fromLngLat([refLon, refLat], 0);
    const s = refMc.meterInMercatorCoordinateUnits();

    modelTransform = {
      translateX: refMc.x,
      translateY: refMc.y,
      translateZ: refMc.z,
      scale: s,
    };

    // Convert waypoints to local Three.js coords (Y-up convention):
    //   localX = east offset (meters)
    //   localY = altitude (meters, up)
    //   localZ = south offset (meters, positive = south)
    // Model transform maps: X→mercX, Z→mercY(south), Y→mercZ(alt)
    const localWps = waypoints.map(wp => {
      const mc = maplibregl.MercatorCoordinate.fromLngLat([wp.lon, wp.lat], 0);
      return {
        seq: wp.seq,
        x: (mc.x - refMc.x) / s,
        y: (wp.groundElev + wp.displayAgl) * terrainExaggeration,
        z: (mc.y - refMc.y) / s,
        groundY: wp.groundElev * terrainExaggeration,
      };
    });

    // 1. Flight path — per-segment colored ribbon meshes (real 3D geometry)
    //    Uses cross-shaped ribbons (horizontal + vertical quads) so the path
    //    is visible from all camera angles. MeshBasicMaterial works correctly
    //    with MapLibre's combined projectionMatrix (no modelViewMatrix needed).
    if (localWps.length >= 2) {
      const hw = FLIGHT_PATH_WIDTH / 2;

      for (let i = 0; i < localWps.length - 1; i++) {
        const from = localWps[i]!;
        const to = localWps[i + 1]!;
        const segColor = data.segmentColors[i] ?? '#3b82f6';

        // Horizontal perpendicular direction in XZ plane
        const dx = to.x - from.x;
        const dz = to.z - from.z;
        const lenXZ = Math.sqrt(dx * dx + dz * dz);
        let hpx: number, hpz: number;
        if (lenXZ > 0.001) {
          hpx = (-dz / lenXZ) * hw;
          hpz = (dx / lenXZ) * hw;
        } else {
          hpx = hw;
          hpz = 0;
        }

        // Cross-shaped ribbon: horizontal quad + vertical quad (12 vertices)
        const positions = new Float32Array([
          // Horizontal ribbon (visible when looking down)
          from.x - hpx, from.y, from.z - hpz,
          from.x + hpx, from.y, from.z + hpz,
          to.x + hpx, to.y, to.z + hpz,
          from.x - hpx, from.y, from.z - hpz,
          to.x + hpx, to.y, to.z + hpz,
          to.x - hpx, to.y, to.z - hpz,
          // Vertical ribbon (visible from the side)
          from.x, from.y - hw, from.z,
          from.x, from.y + hw, from.z,
          to.x, to.y + hw, to.z,
          from.x, from.y - hw, from.z,
          to.x, to.y + hw, to.z,
          to.x, to.y - hw, to.z,
        ]);

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

        const material = new THREE.MeshBasicMaterial({
          color: new THREE.Color(segColor),
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.85,
          depthWrite: false,
        });

        const mesh = new THREE.Mesh(geometry, material);
        mesh.frustumCulled = false;
        scene.add(mesh);
        flightPathSegments.push({ mesh, geometry, material });
      }
    }

    // 2. Drop lines — vertical lines from altitude to ground
    {
      const positions: number[] = [];
      for (const wp of localWps) {
        positions.push(wp.x, wp.y, wp.z);       // at altitude
        positions.push(wp.x, wp.groundY, wp.z);  // at terrain surface
      }

      const geom = new THREE.BufferGeometry();
      geom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

      const mat = new THREE.LineDashedMaterial({
        color: DROP_LINE_COLOR,
        transparent: true,
        opacity: DROP_LINE_OPACITY,
        dashSize: 5,
        gapSize: 5,
      });

      dropLinesObj = new THREE.LineSegments(geom, mat);
      dropLinesObj.computeLineDistances();
      dropLinesObj.frustumCulled = false;
      scene.add(dropLinesObj);
    }

    // 3. DOM markers — HTML elements projected to screen space each frame
    if (markerContainer) {
      for (let i = 0; i < localWps.length; i++) {
        const wp = localWps[i]!;
        const srcWp = waypoints[i]!;
        const isSelected = wp.seq === selectedSeq;

        const size = isSelected ? MARKER_SELECTED_SIZE : MARKER_SIZE;
        const borderColor = isSelected ? 'white' : 'rgba(255,255,255,0.8)';
        const borderWidth = isSelected ? 3 : 2;

        const el = document.createElement('div');
        el.style.cssText =
          'position:absolute;left:0;top:0;pointer-events:auto;cursor:pointer;will-change:transform;display:none;';

        el.innerHTML = `<div style="
          width:${size}px;height:${size}px;border-radius:50%;
          background:${srcWp.color};
          border:${borderWidth}px solid ${borderColor};
          box-shadow:0 2px 6px rgba(0,0,0,0.4);
          display:flex;align-items:center;justify-content:center;
          font-size:${isSelected ? 13 : 12}px;font-weight:bold;color:white;
          user-select:none;
        ">${srcWp.displayText}</div>`;

        el.addEventListener('click', (e) => {
          e.stopPropagation();
          onWaypointClick?.(wp.seq);
        });

        markerContainer.appendChild(el);
        domMarkers.push({
          seq: wp.seq,
          localX: wp.x,
          localY: wp.y,
          localZ: wp.z,
          element: el,
        });
      }
    }
  }

  // ─── MapLibre custom layer (official pattern) ────────────────────────────

  const layer: CustomLayerInterface = {
    id: 'mission-threejs',
    type: 'custom',
    renderingMode: '3d',

    onAdd(m, gl) {
      map = m;
      renderer = new THREE.WebGLRenderer({
        canvas: m.getCanvas(),
        context: gl,
        antialias: true,
      });
      renderer.autoClear = false;
    },

    render(_gl, args: CustomRenderMethodInput) {
      if (!renderer || !map) return;

      // Build model transform: local meters → Mercator world
      // Pattern: Translation * Scale(s, -s, s) * RotateX(π/2)
      const { translateX, translateY, translateZ, scale: s } = modelTransform;

      const l = new THREE.Matrix4()
        .makeTranslation(translateX, translateY, translateZ)
        .scale(new THREE.Vector3(s, -s, s))
        .multiply(rotationX);

      // Use defaultProjectionData.mainMatrix (Mercator → clip space)
      const m = new THREE.Matrix4().fromArray(
        args.defaultProjectionData.mainMatrix as number[],
      );

      // camera.projectionMatrix = mainMatrix * modelTransform
      camera.projectionMatrix = m.multiply(l);

      // Project DOM markers to screen space
      if (domMarkers.length > 0) {
        const canvas = map.getCanvas();
        const cw = canvas.clientWidth;
        const ch = canvas.clientHeight;
        const proj = camera.projectionMatrix;

        for (const marker of domMarkers) {
          const v = new THREE.Vector4(marker.localX, marker.localY, marker.localZ, 1.0);
          v.applyMatrix4(proj);

          if (v.w <= 0) {
            marker.element.style.display = 'none';
            continue;
          }

          const invW = 1 / v.w;
          const sx = (v.x * invW * 0.5 + 0.5) * cw;
          const sy = (1 - (v.y * invW * 0.5 + 0.5)) * ch;

          // Cull off-screen markers
          if (sx < -60 || sx > cw + 60 || sy < -60 || sy > ch + 60) {
            marker.element.style.display = 'none';
            continue;
          }

          marker.element.style.display = '';
          marker.element.style.transform = `translate(${sx}px,${sy}px) translate(-50%,-50%)`;
          // Z-order: closer markers render on top
          marker.element.style.zIndex = String(Math.round(10000 - v.z * invW * 1000));
        }
      }

      renderer.resetState();
      renderer.render(scene, camera);
      map.triggerRepaint();
    },

    onRemove() {
      clearScene();
      renderer?.dispose();
      renderer = null;
      map = null;
    },
  };

  // ─── Public API ──────────────────────────────────────────────────────────

  function setMarkerContainer(container: HTMLDivElement | null) {
    markerContainer = container;
  }

  function updateData(data: MissionLayerData) {
    rebuildScene(data);
    map?.triggerRepaint();
  }

  function dispose() {
    if (map && map.getLayer('mission-threejs')) {
      map.removeLayer('mission-threejs');
    }
    clearScene();
    renderer?.dispose();
    renderer = null;
    map = null;
  }

  return { layer, updateData, setMarkerContainer, dispose };
}
