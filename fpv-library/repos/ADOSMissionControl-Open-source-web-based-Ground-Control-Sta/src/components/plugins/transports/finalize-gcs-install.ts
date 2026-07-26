/**
 * @module FinalizeGcsInstall
 * @description The GCS-side completion of a plugin install. Every
 * transport (LAN-direct file, cloud-relay, registry-from-URL) hands the
 * agent its archive; this step records the install on the GCS side so
 * the operator's Plugins list reflects it AND — for a plugin that ships
 * a GCS half — extracts the built iframe bundle, wraps it in a minimal
 * null-origin HTML shell, uploads that to Convex `_storage`, and records
 * the slot contributions so the live contribution producer
 * (`use-plugin-contributions`) mounts the plugin's sandboxed iframes.
 *
 * Why a shell, not the raw bundle: `PluginIframeHost` sets the iframe
 * `src` to the stored artifact and the sandbox (`allow-scripts`, no
 * `allow-same-origin`) loads it at a null origin. The build emits an ESM
 * module (`gcs/plugin.bundle.js`) which a browser cannot execute as a
 * document, so the host needs an HTML page that inlines the module. The
 * plugin's `definePlugin(...)` boots on module load and creates its own
 * mount node under `document.body`, so the shell only needs a body.
 *
 * Why this runs on the GCS, not the agent: the agent never uploads to
 * Convex storage, and the iframe bundle must live where the browser can
 * fetch it. The registry grid is itself Convex-served, so a registry
 * install always has Convex available; a local-file install already
 * holds the archive bytes. For a registry install the archive bytes are
 * fetched through the same-origin `/api/registry-archive` proxy so the
 * browser is not subject to the release CDN's cross-origin policy.
 *
 * @license GPL-3.0-only
 */

import JSZip from "jszip";

import type { InstallManifestSummary } from "../install-dialog/types";
import type { PluginParameter } from "@/lib/plugins/parameters/schema";
import type { PairedNodeProfile } from "@/lib/plugins/types";
import {
  buildGcsContributes,
  buildGcsParameters,
  buildGcsFlightSkills,
  buildGcsTargetActions,
  type InstallFlightSkill,
  type InstallTargetAction,
} from "./build-install-contributions";

/** The canonical GCS bundle path inside a `.adosplug`. The packer
 * asserts this entry exists before publishing, and the manifest schema
 * fixes the gcs entrypoint to it. */
const GCS_BUNDLE_PATH = "gcs/plugin.bundle.js";

/** Convex `source` discriminator for the install row. */
export type InstallSourceKind = "local_file" | "git_url" | "registry" | "builtin";

/** Convex callables the finalize step needs. Typed loosely so the dialog
 * hands in the result of `useAction(...)` / `useMutation(...)` directly;
 * the server validators own the authoritative shapes. */
export interface GcsInstallCallables {
  /** Returns a one-shot Convex `_storage` upload URL. */
  generateUploadUrl: () => Promise<string>;
  /** Records the install row; returns the new install id. */
  recordInstall: (args: RecordInstallArgs) => Promise<string>;
  /** Grants one operator-approved declared permission. */
  grantPermission: (args: {
    installId: string;
    permissionId: string;
  }) => Promise<unknown>;
  /** Flips the install lifecycle status. */
  setStatus: (args: { installId: string; status: string }) => Promise<unknown>;
}

export interface RecordInstallArgs {
  droneId?: string;
  pluginId: string;
  version: string;
  name: string;
  source: InstallSourceKind;
  sourceUri?: string;
  signerId?: string;
  manifestHash: string;
  halves: string[];
  declaredPermissions: Array<{ id: string; required: boolean }>;
  bundleStorageId?: string;
  gcsContributes?: Array<{
    slot: string;
    panelId: string;
    title?: string;
    icon?: string;
    order?: number;
    profile?: PairedNodeProfile[];
  }>;
  /** Denormalized declarative parameter contributions from the manifest, so
   * the native parameter panel renders without a manifest re-fetch. */
  gcsParameters?: PluginParameter[];
  /** Denormalized flight-skill contributions, so the cockpit Skill Bar mounts
   * the plugin skill for a cloud operator without a manifest re-fetch. */
  flightSkills?: InstallFlightSkill[];
  /** Denormalized cockpit target-action contributions, so the click-a-target
   * popup lists them for a cloud operator without a manifest re-fetch. */
  targetActions?: InstallTargetAction[];
}

export interface FinalizeGcsInstallInputs {
  /** The archive bytes when the GCS already holds them (file/cloud). */
  archive?: Blob;
  /** Canonical archive URL when the GCS must fetch them (registry). */
  archiveUrl?: string;
  manifest: InstallManifestSummary & { manifestHash?: string };
  /** Manifest hash from the dialog's parse (authoritative identity). */
  manifestHash: string;
  /** Operator-approved permission ids. */
  grantedPermissions: ReadonlyArray<string>;
  /** Target drone wire id, or null for a fleet-wide GCS-only plugin. */
  deviceId: string | null;
  source: InstallSourceKind;
  /** Origin URI recorded on the install row (the registry URL). */
  sourceUri?: string;
  callables: GcsInstallCallables;
  /** Injected for tests; defaults to the browser `fetch`. */
  fetchImpl?: typeof fetch;
}

export class FinalizeGcsInstallError extends Error {
  readonly stage: FinalizeStage;
  constructor(stage: FinalizeStage, message: string) {
    super(message);
    this.name = "FinalizeGcsInstallError";
    this.stage = stage;
  }
}

export type FinalizeStage =
  | "fetch-archive"
  | "extract-bundle"
  | "upload-bundle"
  | "record"
  | "grant"
  | "enable";

/**
 * Wrap an ESM plugin bundle in a minimal HTML document the sandboxed
 * iframe can load and execute. The `</script` escape keeps a bundle that
 * happens to contain that byte sequence (in a string literal) from
 * closing the inline module early.
 */
export function buildIframeHtml(bundleJs: string): string {
  const safe = bundleJs.replace(/<\/(script)/gi, "<\\/$1");
  return [
    "<!doctype html>",
    '<html lang="en">',
    "<head>",
    '<meta charset="utf-8">',
    '<meta name="color-scheme" content="dark light">',
    "<style>html,body{margin:0;padding:0;height:100%;background:transparent;overflow:hidden}</style>",
    "</head>",
    "<body>",
    `<script type="module">\n${safe}\n</script>`,
    "</body>",
    "</html>",
  ].join("");
}

/**
 * Complete a plugin install on the GCS side. Returns the new install id,
 * or null when there was nothing to do. Throws `FinalizeGcsInstallError`
 * with a stage tag on any wire failure so the caller can surface a
 * precise, non-fatal notice (the agent half installs regardless).
 */
export async function finalizeGcsInstall(
  inputs: FinalizeGcsInstallInputs,
): Promise<string | null> {
  const { manifest, callables } = inputs;
  const doFetch = inputs.fetchImpl ?? fetch;
  const hasGcsHalf = manifest.halves.includes("gcs");

  let bundleStorageId: string | undefined;
  let gcsContributes: RecordInstallArgs["gcsContributes"];
  // Declarative parameters, flight skills, and target actions are recorded for
  // every plugin that declares them, independent of whether it ships an iframe
  // GCS half — a skill / target-action drives a cockpit behavior with no iframe.
  const gcsParameters = buildGcsParameters(manifest);
  const flightSkills = buildGcsFlightSkills(manifest);
  const targetActions = buildGcsTargetActions(manifest);

  if (hasGcsHalf) {
    // 1. Obtain the archive bytes.
    let archive: Blob;
    if (inputs.archive) {
      archive = inputs.archive;
    } else if (inputs.archiveUrl) {
      let res: Response;
      try {
        res = await doFetch(
          `/api/registry-archive?url=${encodeURIComponent(inputs.archiveUrl)}`,
        );
      } catch (err) {
        throw new FinalizeGcsInstallError(
          "fetch-archive",
          err instanceof Error ? err.message : String(err),
        );
      }
      if (!res.ok) {
        throw new FinalizeGcsInstallError(
          "fetch-archive",
          `archive fetch failed: HTTP ${res.status}`,
        );
      }
      archive = await res.blob();
    } else {
      throw new FinalizeGcsInstallError(
        "fetch-archive",
        "no archive bytes or url supplied for a GCS-half plugin",
      );
    }

    // 2. Extract the built GCS bundle.
    let bundleJs: string;
    try {
      const zip = await JSZip.loadAsync(archive);
      const entry =
        zip.file(GCS_BUNDLE_PATH) ?? zip.file(`./${GCS_BUNDLE_PATH}`);
      if (!entry) {
        throw new Error(`archive is missing ${GCS_BUNDLE_PATH}`);
      }
      bundleJs = await entry.async("string");
    } catch (err) {
      throw new FinalizeGcsInstallError(
        "extract-bundle",
        err instanceof Error ? err.message : String(err),
      );
    }

    // 3. Wrap + upload the iframe document to Convex storage.
    try {
      const uploadUrl = await callables.generateUploadUrl();
      const html = buildIframeHtml(bundleJs);
      const resp = await doFetch(uploadUrl, {
        method: "POST",
        headers: { "Content-Type": "text/html" },
        body: new Blob([html], { type: "text/html" }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const body = (await resp.json()) as { storageId?: string };
      if (!body.storageId) throw new Error("upload returned no storageId");
      bundleStorageId = body.storageId;
    } catch (err) {
      throw new FinalizeGcsInstallError(
        "upload-bundle",
        err instanceof Error ? err.message : String(err),
      );
    }

    gcsContributes = buildGcsContributes(manifest);
  }

  // 4. Record the install row (every install, GCS half or not).
  let installId: string;
  try {
    installId = await callables.recordInstall({
      droneId: inputs.deviceId ?? undefined,
      pluginId: manifest.pluginId,
      version: manifest.version,
      name: manifest.name,
      source: inputs.source,
      sourceUri: inputs.sourceUri,
      signerId: manifest.signerId,
      manifestHash: inputs.manifestHash,
      halves: [...manifest.halves],
      declaredPermissions: manifest.permissions.map((p) => ({
        id: p.id,
        required: p.required,
      })),
      bundleStorageId,
      gcsContributes,
      gcsParameters,
      flightSkills,
      targetActions,
    });
  } catch (err) {
    throw new FinalizeGcsInstallError(
      "record",
      err instanceof Error ? err.message : String(err),
    );
  }

  // 5. Grant the operator-approved permissions. Only ids the manifest
  // declared are grantable; the server rejects anything else.
  const declared = new Set(manifest.permissions.map((p) => p.id));
  for (const permissionId of inputs.grantedPermissions) {
    if (!declared.has(permissionId)) continue;
    try {
      await callables.grantPermission({ installId, permissionId });
    } catch (err) {
      throw new FinalizeGcsInstallError(
        "grant",
        err instanceof Error ? err.message : String(err),
      );
    }
  }

  // 6. Enable so the contribution producer mounts the GCS half. The
  // producer filters to enabled/running installs.
  try {
    await callables.setStatus({ installId, status: "enabled" });
  } catch (err) {
    throw new FinalizeGcsInstallError(
      "enable",
      err instanceof Error ? err.message : String(err),
    );
  }

  return installId;
}
