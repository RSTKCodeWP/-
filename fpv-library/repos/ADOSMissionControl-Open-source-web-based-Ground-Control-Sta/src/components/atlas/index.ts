/**
 * @module atlas
 * @description The first-party World Model viewer utilities. These are the
 * shared, reusable rendering primitives for a reconstructed 3D world (gaussian
 * splat / point cloud / Rerun world) — composed today by the drone World Model
 * feature and the workstation Forge workbench, and the reuse surface for any
 * future feature or plugin viewer host.
 *
 *  - {@link WorldModelViewport} — the code-split viewer dispatcher (`{viewer,
 *    artifactUrl, backend}` in, the selected WASM/WebGL viewer out).
 *  - {@link ViewerSwitcher} — the World / Splat / Cloud / LOD toolbar.
 *  - viewer-types — the `AtlasViewer` union, the `ATLAS_VIEWERS` registry, and
 *    the artifact/hint resolution helpers.
 *
 * Each leaf viewer (`viewers/*`) is a pure `{url}` component with no store
 * coupling; import them via {@link WorldModelViewport}, not directly, so the
 * dynamic-import code-splitting is preserved.
 *
 * @license GPL-3.0-only
 */

export { WorldModelViewport } from "./WorldModelViewport";
export { ViewerSwitcher } from "./ViewerSwitcher";
export { ReconstructionBadge } from "./ReconstructionBadge";
export {
  ATLAS_VIEWERS,
  DEFAULT_ATLAS_VIEWER,
  viewerHintOf,
  viewerForKind,
  backendOf,
  pickArtifactForViewer,
  type AtlasViewer,
  type AtlasViewerSpec,
} from "./viewer-types";
