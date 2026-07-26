/**
 * Three.js custom layer for MapLibre GL — renders a 3D vehicle model
 * with attitude visualization, altitude drop line, and ground ring.
 *
 * Same pattern as mission-threejs-layer.ts: separate scene, shared WebGL context.
 */
import * as THREE from 'three';
import maplibregl, { type CustomLayerInterface, type CustomRenderMethodInput } from 'maplibre-gl';

// ─── Public types ────────────────────────────────────────────────────────────

export interface VehicleLayerState {
  /** Vehicle position [lon, lat] */
  lngLat: [number, number] | null;
  /** Heading in degrees (0=north, CW positive) */
  heading: number;
  /** Roll in degrees (positive = right wing down) */
  roll: number;
  /** Pitch in degrees (positive = nose up) */
  pitch: number;
  /** Altitude above ground level in meters */
  altitudeAgl: number;
  /** Whether the vehicle is armed */
  armed: boolean;
  /** Terrain exaggeration factor from the map */
  terrainExaggeration: number;
  /** Real-world vehicle size in meters (wingspan, frameSize diagonal, etc.) */
  vehicleSizeMeters: number;
  /** When true, use real-world size from profile. When false, auto-scale to stay visible. */
  useRealSize: boolean;
  /** Whether to show the 3D heading line */
  showHeadingLine: boolean;
  /** Heading line length in meters (default 100) */
  headingLineLength: number;
  /** Heading line color as hex string (e.g. '#22d3ee') */
  headingLineColor: string;
}

export interface VehicleThreeJsLayer {
  layer: CustomLayerInterface;
  updateState: (state: VehicleLayerState) => void;
  dispose: () => void;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const DEG2RAD = Math.PI / 180;
const COLOR_DISARMED = 0x22d3ee; // cyan
const COLOR_ARMED = 0xf97316;    // orange
const OUTLINE_COLOR = 0xffffff;
const DROP_LINE_COLOR = 0x9ca3af;
const MIN_ALT_FOR_DROPLINE = 0.5; // meters
const AUTO_SCREEN_PX = 45; // auto-size mode: constant screen size
const HEADING_LINE_BASE_W = 0.35; // meters — ribbon half-width at vehicle end
const HEADING_LINE_TIP_W = 0.06;  // meters — tapers to this at the far end

// ─── Geometry builders ───────────────────────────────────────────────────────

/** Build the arrow/chevron shape matching the 2D SVG "M12 2L4 20l8-4 8 4L12 2z" */
function buildArrowShape(): THREE.Shape {
  // SVG coords: tip=(12,2), left=(4,20), notch=(12,16), right=(20,20)
  // Center at (12,11) and scale to ~3m wingspan
  const scale = 3 / 16; // 16 SVG units → 3 meters
  const cx = 12, cy = 11;

  const shape = new THREE.Shape();
  // Start at tip (nose)
  shape.moveTo((12 - cx) * scale, (cy - 2) * scale);
  // Left wing
  shape.lineTo((4 - cx) * scale, (cy - 20) * scale);
  // Notch (tail center)
  shape.lineTo((12 - cx) * scale, (cy - 16) * scale);
  // Right wing
  shape.lineTo((20 - cx) * scale, (cy - 20) * scale);
  // Close back to tip
  shape.closePath();

  return shape;
}

/** Build a small triangular tail fin shape */
function buildTailFinShape(): THREE.Shape {
  const shape = new THREE.Shape();
  // Small triangle sitting at the tail
  shape.moveTo(0, 0);
  shape.lineTo(-0.3, -1.2);
  shape.lineTo(0.3, -1.2);
  shape.closePath();
  return shape;
}

// ─── Factory ─────────────────────────────────────────────────────────────────

export function createVehicleThreeJsLayer(): VehicleThreeJsLayer {
  let map: maplibregl.Map | null = null;
  let renderer: THREE.WebGLRenderer | null = null;
  const camera = new THREE.Camera();
  const scene = new THREE.Scene();

  // Precomputed rotation matrix (constant π/2 around X)
  const rotationX = new THREE.Matrix4().makeRotationAxis(
    new THREE.Vector3(1, 0, 0),
    Math.PI / 2,
  );

  // Model transform params
  let modelTransform = {
    translateX: 0,
    translateY: 0,
    translateZ: 0,
    scale: 1,
  };

  // Current state
  let currentState: VehicleLayerState | null = null;

  // Scene objects
  let vehicleGroup: THREE.Group | null = null;
  let bodyMesh: THREE.Mesh | null = null;
  let outlineMesh: THREE.Mesh | null = null;
  let finMesh: THREE.Mesh | null = null;
  let finOutlineMesh: THREE.Mesh | null = null;
  let dropLine: THREE.LineSegments | null = null;
  let groundRing: THREE.Mesh | null = null;

  // Heading line (separate group — yaw-only, no roll/pitch)
  let headingLineGroup: THREE.Group | null = null;
  let headingLineMeshes: THREE.Mesh[] = [];

  // Lighting
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(1, 2, 1).normalize();
  scene.add(ambientLight);
  scene.add(dirLight);

  // Shared geometries — created once
  let arrowGeometry: THREE.ExtrudeGeometry | null = null;
  let finGeometry: THREE.ExtrudeGeometry | null = null;
  let ringGeometry: THREE.RingGeometry | null = null;

  function ensureGeometries() {
    if (!arrowGeometry) {
      const arrowShape = buildArrowShape();
      arrowGeometry = new THREE.ExtrudeGeometry(arrowShape, {
        depth: 0.5,
        bevelEnabled: true,
        bevelThickness: 0.08,
        bevelSize: 0.08,
        bevelSegments: 2,
      });
      // Center the geometry so rotation is around the centroid
      arrowGeometry.computeBoundingBox();
      arrowGeometry.center();
    }

    if (!finGeometry) {
      const finShape = buildTailFinShape();
      finGeometry = new THREE.ExtrudeGeometry(finShape, {
        depth: 0.08,
        bevelEnabled: false,
      });
      finGeometry.center();
    }

    if (!ringGeometry) {
      ringGeometry = new THREE.RingGeometry(1.5, 2.0, 32);
      // Rotate ring to lie flat on XZ plane
      ringGeometry.rotateX(-Math.PI / 2);
    }
  }

  function clearScene() {
    if (vehicleGroup) {
      scene.remove(vehicleGroup);
      vehicleGroup = null;
    }
    if (dropLine) {
      scene.remove(dropLine);
      dropLine.geometry.dispose();
      (dropLine.material as THREE.Material).dispose();
      dropLine = null;
    }
    if (groundRing) {
      scene.remove(groundRing);
      // Geometry is shared, only dispose material
      (groundRing.material as THREE.Material).dispose();
      groundRing = null;
    }
    if (headingLineGroup) {
      for (const mesh of headingLineMeshes) {
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
      }
      scene.remove(headingLineGroup);
      headingLineGroup = null;
      headingLineMeshes = [];
    }
    bodyMesh = null;
    outlineMesh = null;
    finMesh = null;
    finOutlineMesh = null;
  }

  function rebuildScene(state: VehicleLayerState) {
    clearScene();
    if (!state.lngLat) return;

    ensureGeometries();

    const [lon, lat] = state.lngLat;
    const refMc = maplibregl.MercatorCoordinate.fromLngLat([lon, lat], 0);
    const s = refMc.meterInMercatorCoordinateUnits();

    modelTransform = {
      translateX: refMc.x,
      translateY: refMc.y,
      translateZ: refMc.z,
      scale: s,
    };

    const color = state.armed ? COLOR_ARMED : COLOR_DISARMED;

    // Vehicle group — attitude rotations (heading/pitch/roll)
    // Y position is set to 0 here; the render loop updates it every frame
    // based on live terrain queries (handles async DEM tile loading).
    vehicleGroup = new THREE.Group();
    vehicleGroup.position.set(0, 0, 0);

    // Apply attitude rotations (Euler YXZ)
    vehicleGroup.rotation.order = 'YXZ';
    vehicleGroup.rotation.y = -state.heading * DEG2RAD;
    vehicleGroup.rotation.x = state.pitch * DEG2RAD;
    vehicleGroup.rotation.z = -state.roll * DEG2RAD;

    // Model group — base rotation to lay the geometry flat.
    // The arrow is built in the XY plane (nose at +Y, extruded along Z).
    // In the scene, Y is up. Rotating -90° around X lays the model in the
    // XZ plane with nose pointing -Z (north when heading=0).
    const modelGroup = new THREE.Group();
    modelGroup.rotation.x = -Math.PI / 2;

    // Body mesh
    const bodyMat = new THREE.MeshLambertMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.3,
    });
    bodyMesh = new THREE.Mesh(arrowGeometry!, bodyMat);
    bodyMesh.frustumCulled = false;
    modelGroup.add(bodyMesh);

    // Outline mesh (BackSide, slightly larger)
    const outlineMat = new THREE.MeshBasicMaterial({
      color: OUTLINE_COLOR,
      side: THREE.BackSide,
    });
    outlineMesh = new THREE.Mesh(arrowGeometry!, outlineMat);
    outlineMesh.scale.set(1.08, 1.08, 1.08);
    outlineMesh.frustumCulled = false;
    modelGroup.add(outlineMesh);

    // Tail fin (vertical on top of body)
    const finMat = new THREE.MeshLambertMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.3,
    });
    finMesh = new THREE.Mesh(finGeometry!, finMat);
    // Position at the tail area, rotated to stand vertical
    finMesh.position.set(0, 0.4, -0.5);
    finMesh.rotation.x = Math.PI / 2;
    finMesh.frustumCulled = false;
    modelGroup.add(finMesh);

    // Fin outline
    const finOutlineMat = new THREE.MeshBasicMaterial({
      color: OUTLINE_COLOR,
      side: THREE.BackSide,
    });
    finOutlineMesh = new THREE.Mesh(finGeometry!, finOutlineMat);
    finOutlineMesh.position.copy(finMesh.position);
    finOutlineMesh.rotation.copy(finMesh.rotation);
    finOutlineMesh.scale.set(1.1, 1.1, 1.1);
    finOutlineMesh.frustumCulled = false;
    modelGroup.add(finOutlineMesh);

    vehicleGroup.add(modelGroup);
    scene.add(vehicleGroup);

    // Drop line — vertical dashed line from vehicle to ground
    // Y values are placeholders; the render loop updates them every frame.
    if (state.altitudeAgl >= MIN_ALT_FOR_DROPLINE) {
      const linePositions = new Float32Array([
        0, 0, 0,
        0, 0, 0,
      ]);
      const lineGeom = new THREE.BufferGeometry();
      lineGeom.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));

      const lineMat = new THREE.LineDashedMaterial({
        color: DROP_LINE_COLOR,
        transparent: true,
        opacity: 0.4,
        dashSize: 3,
        gapSize: 3,
      });

      dropLine = new THREE.LineSegments(lineGeom, lineMat);
      dropLine.computeLineDistances();
      dropLine.frustumCulled = false;
      scene.add(dropLine);
    }

    // Ground ring — flat ring at terrain level
    // Y is a placeholder; the render loop updates it every frame.
    if (state.altitudeAgl >= MIN_ALT_FOR_DROPLINE) {
      const ringMat = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.3,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      groundRing = new THREE.Mesh(ringGeometry!, ringMat);
      groundRing.position.set(0, 0, 0);
      groundRing.frustumCulled = false;
      scene.add(groundRing);
    }

    // Heading line — thin tapered ribbon extending from vehicle in heading direction.
    // Separate group (not child of vehicleGroup) so it only follows yaw, not roll/pitch.
    if (state.showHeadingLine) {
      const lineLen = state.headingLineLength;
      const lineColor = new THREE.Color(state.headingLineColor);

      headingLineGroup = new THREE.Group();
      headingLineGroup.rotation.order = 'YXZ';
      headingLineGroup.rotation.y = -state.heading * DEG2RAD;
      headingLineMeshes = [];

      // Tapered flat ribbon on the XZ plane. Wide at origin, narrow at -Z tip.
      const buildTaperedRibbon = (baseHW: number, tipHW: number): THREE.BufferGeometry => {
        const geom = new THREE.BufferGeometry();
        // Two triangles forming a tapered quad
        const positions = new Float32Array([
          -baseHW, 0, 0,    baseHW, 0, 0,    tipHW, 0, -lineLen,
          -baseHW, 0, 0,    tipHW, 0, -lineLen,  -tipHW, 0, -lineLen,
        ]);
        geom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        geom.computeVertexNormals();
        return geom;
      };

      // Dark outline — provides contrast on any background
      const darkGeom = buildTaperedRibbon(HEADING_LINE_BASE_W * 1.6, HEADING_LINE_TIP_W * 1.6);
      const darkMat = new THREE.MeshBasicMaterial({
        color: 0x000000, transparent: true, opacity: 0.6,
        side: THREE.DoubleSide, depthWrite: false,
        polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
      });
      const darkMesh = new THREE.Mesh(darkGeom, darkMat);
      darkMesh.frustumCulled = false;
      darkMesh.renderOrder = 10;
      headingLineGroup.add(darkMesh);
      headingLineMeshes.push(darkMesh);

      // Colored fill — vehicle color, fully opaque
      const colorGeom = buildTaperedRibbon(HEADING_LINE_BASE_W, HEADING_LINE_TIP_W);
      const colorMat = new THREE.MeshBasicMaterial({
        color: lineColor, side: THREE.DoubleSide, depthWrite: false,
        polygonOffset: true, polygonOffsetFactor: -3, polygonOffsetUnits: -3,
      });
      const colorMesh = new THREE.Mesh(colorGeom, colorMat);
      colorMesh.frustumCulled = false;
      colorMesh.renderOrder = 11;
      headingLineGroup.add(colorMesh);
      headingLineMeshes.push(colorMesh);

      scene.add(headingLineGroup);
    }
  }

  // ─── MapLibre custom layer ────────────────────────────────────────────────

  const layer: CustomLayerInterface = {
    id: 'vehicle-threejs',
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
      if (!renderer || !map || !currentState?.lngLat) return;

      const [lon, lat] = currentState.lngLat;

      // Use static model transform from rebuildScene (origin at sea level).
      // Same pattern as mission-threejs-layer: sea-level origin, terrain as Y offset.
      const { translateX, translateY, translateZ, scale: s } = modelTransform;

      const l = new THREE.Matrix4()
        .makeTranslation(translateX, translateY, translateZ)
        .scale(new THREE.Vector3(s, -s, s))
        .multiply(rotationX);

      const m = new THREE.Matrix4().fromArray(
        args.defaultProjectionData.mainMatrix as number[],
      );

      camera.projectionMatrix = m.multiply(l);

      if (vehicleGroup) {
        // Query terrain elevation every frame (returns visual meters including exaggeration,
        // or null if terrain data isn't loaded yet).
        let terrainY = 0;
        const elev = map.queryTerrainElevation(new maplibregl.LngLat(lon, lat));
        if (elev !== null && elev !== undefined) {
          terrainY = elev;
        }

        // Vehicle Y = terrain surface + AGL offset.
        // Matches mission-threejs-layer pattern: (groundElev + displayAgl) * exaggeration.
        // terrainY already includes exaggeration, so only AGL needs scaling.
        const altY = currentState.altitudeAgl * currentState.terrainExaggeration;
        vehicleGroup.position.y = terrainY + altY;

        // Update drop line endpoints
        if (dropLine) {
          const positions = dropLine.geometry.getAttribute('position') as THREE.BufferAttribute;
          positions.setY(0, terrainY + altY);
          positions.setY(1, terrainY);
          positions.needsUpdate = true;
        }

        // Ground ring at terrain surface
        if (groundRing) {
          groundRing.position.y = terrainY + 0.1;
        }

        // The arrow geometry is ~3m wingspan.
        const GEOM_BASE_SIZE = 3; // meters
        let scaleFactor: number;
        if (currentState.useRealSize) {
          // Fixed real-world size from profile — zoom does not affect it
          scaleFactor = currentState.vehicleSizeMeters / GEOM_BASE_SIZE;
        } else {
          // Auto-size: constant ~45px on screen regardless of zoom
          const zoom = map.getZoom();
          const latRad = lat * DEG2RAD;
          const metersPerPixel =
            (156543.03392 * Math.cos(latRad)) / Math.pow(2, zoom);
          scaleFactor = Math.max(1, (metersPerPixel * AUTO_SCREEN_PX) / GEOM_BASE_SIZE);
        }
        vehicleGroup.scale.setScalar(scaleFactor);

        // Heading line — at vehicle altitude + small offset to avoid clipping into buildings
        if (headingLineGroup) {
          headingLineGroup.position.y = terrainY + altY + 2;
          headingLineGroup.rotation.y = -currentState.heading * DEG2RAD;
          // Width scales gently with zoom (visible but not fat). Length stays real meters.
          const lineWidthScale = Math.max(1, scaleFactor * 0.5);
          headingLineGroup.scale.set(lineWidthScale, lineWidthScale, 1);
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

  function updateState(state: VehicleLayerState) {
    currentState = state;
    rebuildScene(state);
    map?.triggerRepaint();
  }

  function dispose() {
    if (map && map.getLayer('vehicle-threejs')) {
      map.removeLayer('vehicle-threejs');
    }
    clearScene();
    arrowGeometry?.dispose();
    arrowGeometry = null;
    finGeometry?.dispose();
    finGeometry = null;
    ringGeometry?.dispose();
    ringGeometry = null;
    renderer?.dispose();
    renderer = null;
    map = null;
  }

  return { layer, updateState, dispose };
}
