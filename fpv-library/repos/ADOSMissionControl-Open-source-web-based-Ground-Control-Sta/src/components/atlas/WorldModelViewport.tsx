"use client";

/**
 * @module atlas/WorldModelViewport
 * @description Renders the selected World Model viewer for an artifact URL. Each
 * viewer is code-split + SSR-disabled via next/dynamic, so a heavy WASM/WebGL
 * bundle loads only when its viewer is selected with a real artifact. Returns
 * null when there is no artifact (the tab shows its empty state).
 * @license GPL-3.0-only
 */

import dynamic from "next/dynamic";
import type { AtlasViewer } from "./viewer-types";
import { ReconstructionBadge } from "./ReconstructionBadge";

const RerunViewer = dynamic(() => import("./viewers/RerunViewer"), {
  ssr: false,
});
const SplatViewer = dynamic(() => import("./viewers/SplatViewer"), {
  ssr: false,
});
const PointCloudViewer = dynamic(() => import("./viewers/PointCloudViewer"), {
  ssr: false,
});
const PointCloudLodViewer = dynamic(
  () => import("./viewers/PointCloudLodViewer"),
  { ssr: false },
);

export function WorldModelViewport({
  viewer,
  artifactUrl,
  backend = null,
}: {
  viewer: AtlasViewer;
  artifactUrl: string | null;
  /** The concrete reconstruction backend for the honesty badge (Rule 44):
   * `"mock"` badges a placeholder, a real backend name badges the reconstructor,
   * null/absent shows nothing. */
  backend?: string | null;
}) {
  if (!artifactUrl) return null;
  const view = (() => {
    switch (viewer) {
      case "rerun":
        return <RerunViewer url={artifactUrl} />;
      case "splat":
        return <SplatViewer url={artifactUrl} />;
      case "cloud":
        return <PointCloudViewer url={artifactUrl} />;
      case "lod":
        return <PointCloudLodViewer url={artifactUrl} />;
      default:
        return null;
    }
  })();
  if (!view) return null;
  return (
    <>
      {view}
      <ReconstructionBadge backend={backend} />
    </>
  );
}
