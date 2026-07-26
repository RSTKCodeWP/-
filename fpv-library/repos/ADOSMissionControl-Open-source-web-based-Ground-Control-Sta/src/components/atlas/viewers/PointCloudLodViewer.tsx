"use client";

/**
 * @module atlas/viewers/PointCloudLodViewer
 * @description The cloud viewer that survives very large `.ply` reconstructions.
 * `PointCloudViewer` puts every vertex on the GPU as one THREE.Points, so a
 * multi-million-point cloud exhausts browser memory; this loads the cloud, then
 * decimates it to a point budget (a single-level voxel-grid pass, `decimateCloud`)
 * and disposes the full geometry — so the retained buffer never exceeds the
 * budget no matter how dense the source. The decimation keeps a spatially uniform
 * subset (one representative per occupied cell) rather than a clumped slice, and
 * a badge states "showing X of Y" so the operator knows the view is decimated
 * (Rule 44). The renderer, orbit controls, geometry, and material are all disposed
 * on unmount / url change on the same WebGL2 context.
 *
 * The transient peak still includes the full parsed file (PLYLoader has no
 * streaming entry point); true out-of-core octree streaming for clouds that don't
 * fit in memory at all stays a follow-on (it is what Potree did, and its loader
 * pins an older three than the repo's 0.183).
 * @license GPL-3.0-only
 */

import { useEffect, useRef, useState } from "react";
import type { BufferGeometry, Material, WebGLRenderer } from "three";
import type { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { ViewerError } from "./ViewerError";
import { ViewerLoading } from "./ViewerLoading";
import { decimateCloud } from "./decimate-cloud";
import { orientCloudToYUp } from "./coordinate-frame";
import {
  fetchArrayBufferWithProgress,
  type FetchProgress,
} from "@/lib/net/fetch-with-progress";

/** Retained-point cap. ~1.5M points = ~18 MB of float positions, GPU-comfortable. */
const LOD_POINT_BUDGET = 1_500_000;

interface CloudStats {
  total: number;
  kept: number;
  decimated: boolean;
}

export default function PointCloudLodViewer({ url }: { url: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<CloudStats | null>(null);
  const [progress, setProgress] = useState<FetchProgress | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setFailed(false);
    setLoading(true);
    setStats(null);
    setProgress(null);
    const abort = new AbortController();
    let raf = 0;
    let disposed = false;
    // Hoisted so the cleanup can release the WebGL context + GPU buffers.
    let renderer: WebGLRenderer | null = null;
    let controls: OrbitControls | null = null;
    let geometry: BufferGeometry | null = null;
    let material: Material | null = null;

    void (async () => {
      try {
        const THREE = await import("three");
        const { PLYLoader } = await import(
          "three/examples/jsm/loaders/PLYLoader.js"
        );
        const { OrbitControls: Orbit } = await import(
          "three/examples/jsm/controls/OrbitControls.js"
        );
        if (disposed || !canvasRef.current) return;

        // Load the full cloud, decimate to the budget, then drop the full copy.
        const buffer = await fetchArrayBufferWithProgress(url, {
          signal: abort.signal,
          onProgress: (p) => {
            if (!disposed) setProgress(p);
          },
        });
        if (disposed) return;
        const full = new PLYLoader().parse(buffer);
        const posAttr = full.getAttribute("position");
        if (!(posAttr instanceof THREE.BufferAttribute)) {
          full.dispose();
          throw new Error("no positions");
        }
        const colAttr = full.getAttribute("color");
        const colors =
          colAttr instanceof THREE.BufferAttribute ? colAttr.array : null;
        const dec = decimateCloud(posAttr.array, colors, LOD_POINT_BUDGET);
        full.dispose();
        if (dec.kept === 0) throw new Error("empty cloud");

        const geom = new THREE.BufferGeometry();
        geom.setAttribute(
          "position",
          new THREE.BufferAttribute(dec.positions, 3),
        );
        if (dec.colors) {
          geom.setAttribute("color", new THREE.BufferAttribute(dec.colors, 3));
        }
        // COLMAP Y-down world frame → viewer Y-up (before the framing sphere).
        orientCloudToYUp(geom);
        geom.computeBoundingSphere();
        geometry = geom;
        setStats({ total: dec.total, kept: dec.kept, decimated: dec.decimated });

        const width = canvas.clientWidth || 640;
        const height = canvas.clientHeight || 360;
        const r = new THREE.WebGLRenderer({ canvas, antialias: false });
        r.setSize(width, height, false);
        renderer = r;

        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0a0a0a);
        const camera = new THREE.PerspectiveCamera(60, width / height, 0.01, 5000);
        const ctrl = new Orbit(camera, canvas);
        controls = ctrl;

        const hasColor = !!dec.colors;
        const mat = new THREE.PointsMaterial({
          size: 0.012,
          sizeAttenuation: true,
          vertexColors: hasColor,
          color: hasColor ? 0xffffff : 0x88ccff,
        });
        material = mat;
        scene.add(new THREE.Points(geom, mat));

        // Frame the cloud from its bounding sphere so it fills the view.
        const bs = geom.boundingSphere;
        if (bs) {
          const dist = Math.max(bs.radius * 2.5, 0.5);
          camera.position.set(bs.center.x, bs.center.y, bs.center.z + dist);
          ctrl.target.copy(bs.center);
        }
        ctrl.update();
        setLoading(false);

        const frame = () => {
          ctrl.update();
          r.render(scene, camera);
          raf = requestAnimationFrame(frame);
        };
        raf = requestAnimationFrame(frame);
      } catch {
        if (!disposed) {
          setLoading(false);
          setFailed(true);
        }
      }
    })();

    return () => {
      disposed = true;
      abort.abort();
      cancelAnimationFrame(raf);
      controls?.dispose();
      geometry?.dispose();
      material?.dispose();
      renderer?.dispose();
    };
  }, [url]);

  return (
    <div className="relative w-full h-full min-h-[320px]">
      <canvas ref={canvasRef} className="w-full h-full" />
      {loading && !failed && (
        <ViewerLoading
          percent={progress?.percent ?? undefined}
          receivedBytes={progress?.receivedBytes}
          totalBytes={progress?.totalBytes ?? undefined}
          label="Downloading cloud"
        />
      )}
      {failed && <ViewerError what="point cloud" />}
      {stats?.decimated && !failed && (
        <div className="absolute bottom-2 left-2 rounded bg-surface-primary/70 px-2 py-1 text-[10px] font-mono text-text-tertiary tabular-nums">
          {`showing ${stats.kept.toLocaleString()} / ${stats.total.toLocaleString()} points`}
        </div>
      )}
    </div>
  );
}
