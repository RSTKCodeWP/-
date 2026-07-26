/**
 * Three.js custom layer for MapLibre GL — renders flight path at altitude
 * with drop lines to ground. Based on mission-threejs-layer.ts pattern.
 */
import * as THREE from 'three';
import maplibregl, { type CustomLayerInterface, type CustomRenderMethodInput } from 'maplibre-gl';

export interface FlightPathPoint {
  lon: number;
  lat: number;
  alt: number; // meters AGL
}

export interface FlightPathLayerData {
  points: FlightPathPoint[];
  /** Ground elevation MSL at the takeoff point. Added to all altitudes so path sits above terrain. */
  groundElevation?: number;
  terrainExaggeration?: number;
  /** Per-segment hex color (length = points.length - 1). If omitted, uses default amber. */
  segmentColors?: string[];
}

export interface FlightPathThreeJsLayer {
  layer: CustomLayerInterface;
  updateData: (data: FlightPathLayerData) => void;
  dispose: () => void;
}

const PATH_WIDTH = 6;
const PATH_COLOR = 0xf59e0b;    // amber
const PATH_OPACITY = 0.9;
const DROP_LINE_COLOR = 0xf59e0b; // amber, matching path
const DROP_LINE_OPACITY = 0.7;
const DROP_LINE_STEP = 15; // every N points

export function createFlightPathThreeJsLayer(): FlightPathThreeJsLayer {
  let map: maplibregl.Map | null = null;
  let renderer: THREE.WebGLRenderer | null = null;
  const camera = new THREE.Camera();
  const scene = new THREE.Scene();

  let modelTransform = { translateX: 0, translateY: 0, translateZ: 0, scale: 1 };
  const rotationX = new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(1, 0, 0), Math.PI / 2);

  const meshes: { mesh: THREE.Mesh; geometry: THREE.BufferGeometry; material: THREE.MeshBasicMaterial }[] = [];
  let dropLinesObj: THREE.LineSegments | null = null;

  function clearScene() {
    for (const m of meshes) {
      scene.remove(m.mesh);
      m.geometry.dispose();
      m.material.dispose();
    }
    meshes.length = 0;
    if (dropLinesObj) {
      scene.remove(dropLinesObj);
      dropLinesObj.geometry.dispose();
      (dropLinesObj.material as THREE.Material).dispose();
      dropLinesObj = null;
    }
  }

  function rebuildScene(data: FlightPathLayerData) {
    clearScene();
    const { points, groundElevation = 0, segmentColors } = data;
    if (points.length < 2) return;

    // Reference point = centroid at ground elevation
    let sumLon = 0, sumLat = 0;
    for (const p of points) { sumLon += p.lon; sumLat += p.lat; }
    const refLon = sumLon / points.length;
    const refLat = sumLat / points.length;

    const refMc = maplibregl.MercatorCoordinate.fromLngLat([refLon, refLat], 0);
    const s = refMc.meterInMercatorCoordinateUnits();
    modelTransform = { translateX: refMc.x, translateY: refMc.y, translateZ: refMc.z, scale: s };

    // Convert to local coords (Y-up: X=east, Y=alt, Z=south)
    // Use groundElevation (MSL) + AGL altitude directly in meters
    // The model transform (scale = meterInMercatorCoordinateUnits) handles conversion
    const local = points.map(p => {
      const mc = maplibregl.MercatorCoordinate.fromLngLat([p.lon, p.lat], 0);
      return {
        x: (mc.x - refMc.x) / s,
        y: groundElevation + p.alt,
        z: (mc.y - refMc.y) / s,
        groundY: groundElevation,
      };
    });

    // Flight path ribbon — cross-shaped (visible from any angle)
    const hw = PATH_WIDTH / 2;
    for (let i = 0; i < local.length - 1; i++) {
      const from = local[i]!;
      const to = local[i + 1]!;

      const dx = to.x - from.x;
      const dz = to.z - from.z;
      const lenXZ = Math.sqrt(dx * dx + dz * dz);
      let hpx: number, hpz: number;
      if (lenXZ > 0.001) { hpx = (-dz / lenXZ) * hw; hpz = (dx / lenXZ) * hw; }
      else { hpx = hw; hpz = 0; }

      const positions = new Float32Array([
        // Horizontal ribbon
        from.x - hpx, from.y, from.z - hpz,
        from.x + hpx, from.y, from.z + hpz,
        to.x + hpx, to.y, to.z + hpz,
        from.x - hpx, from.y, from.z - hpz,
        to.x + hpx, to.y, to.z + hpz,
        to.x - hpx, to.y, to.z - hpz,
        // Vertical ribbon
        from.x, from.y - hw, from.z,
        from.x, from.y + hw, from.z,
        to.x, to.y + hw, to.z,
        from.x, from.y - hw, from.z,
        to.x, to.y + hw, to.z,
        to.x, to.y - hw, to.z,
      ]);

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

      const segColor = segmentColors?.[i] ?? '#f59e0b';
      const material = new THREE.MeshBasicMaterial({
        color: new THREE.Color(segColor),
        side: THREE.DoubleSide,
        transparent: true,
        opacity: PATH_OPACITY,
        depthWrite: false,
      });

      const mesh = new THREE.Mesh(geometry, material);
      mesh.frustumCulled = false;
      scene.add(mesh);
      meshes.push({ mesh, geometry, material });
    }

    // Drop lines — every N points
    {
      const positions: number[] = [];
      for (let i = 0; i < local.length; i += DROP_LINE_STEP) {
        const p = local[i]!;
        if (p.y > p.groundY + 1) {
          positions.push(p.x, p.y, p.z);
          positions.push(p.x, p.groundY, p.z);
        }
      }
      // Always include last point
      const last = local[local.length - 1]!;
      if (last.y > last.groundY + 1) {
        positions.push(last.x, last.y, last.z);
        positions.push(last.x, last.groundY, last.z);
      }

      if (positions.length > 0) {
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
    }
  }

  const layer: CustomLayerInterface = {
    id: 'flight-path-threejs',
    type: 'custom',
    renderingMode: '3d',

    onAdd(m, gl) {
      map = m;
      renderer = new THREE.WebGLRenderer({ canvas: m.getCanvas(), context: gl, antialias: true });
      renderer.autoClear = false;
    },

    render(_gl, args: CustomRenderMethodInput) {
      if (!renderer || !map) return;

      const { translateX, translateY, translateZ, scale: sc } = modelTransform;
      const l = new THREE.Matrix4()
        .makeTranslation(translateX, translateY, translateZ)
        .scale(new THREE.Vector3(sc, -sc, sc))
        .multiply(rotationX);

      const m = new THREE.Matrix4().fromArray(args.defaultProjectionData.mainMatrix as number[]);
      camera.projectionMatrix = m.multiply(l);

      renderer.resetState();
      renderer.render(scene, camera);
    },
  };

  return {
    layer,
    updateData(data: FlightPathLayerData) {
      rebuildScene(data);
      map?.triggerRepaint();
    },
    dispose() {
      clearScene();
    },
  };
}
